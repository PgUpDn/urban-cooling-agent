import os
import glob
import math
import time
import warnings
import hashlib
import json
from collections import deque

import numpy as np
import pandas as pd
import pytz
import datetime as dt
import trimesh
from vedo import Plotter, Mesh, Points, Text2D, write
import pvlib
import matplotlib.pyplot as plt
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree
from pythermalcomfort.models import pet_steady

def _save_screenshot(plotter, filepath, **kwargs):
    """
    Wrapper for vedo Plotter.screenshot that allows overwriting.
    If the file already exists, delete it first, then save.
    Prints messages so we can see what happens.
    """
    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"[Screenshot] Deleted existing file: {filepath}")
        except OSError as e:
            print(f"[Screenshot WARNING] Could not delete existing file: {filepath} ({e})")

    try:
        plotter.screenshot(filepath, **kwargs, scale=4)
        print(f"[Screenshot] Saved screenshot to: {filepath}")
    except Exception as e:
        print(f"[Screenshot ERROR] Could not save screenshot to: {filepath} ({e})")

def calculate_cooling_load(T_out_series, A_surface, k, L, rho, cp, h_in=8.0, T_room=25.0):
    """
    Calculates the cooling load through a surface using a simplified CTF model.
    
    Args:
        T_out_series (np.array): Time series of outside surface temperature (°C).
        A_surface (float): Area of the surface (m²).
        k (float): Thermal conductivity (W/m·K).
        L (float): Thickness (m).
        rho (float): Density (kg/m³).
        cp (float): Specific heat capacity (J/kg·K).
        h_in (float): Interior convective heat transfer coefficient (W/m²·K).
        T_room (float): Constant interior room temperature (°C).

    Returns:
        dict: A dictionary containing 'Q_cooling' (W), 'q_flux' (W/m²), and 'T_inside' (°C).
    """
    tau = rho * cp * L**2 / (np.pi**2 * k) if k > 0 else float('inf') # Time constant (s)
    if tau == 0: return {'Q_cooling': np.zeros_like(T_out_series), 'q_flux': np.zeros_like(T_out_series), 'T_inside': np.full_like(T_out_series, T_room)}

    U = k / L if L > 0 else 0 # Simplified U-value (W/m²·K)
    dt = 3600  # Time step of 1 hour (s)
    
    decay = np.exp(-dt / tau) if tau > 0 else 0
    Y0 = U * (1 - decay)
    Y1 = U * decay
    Phi = decay
    
    n = len(T_out_series)
    q_in = np.zeros(n)
    
    # Apply CTF formula across time series
    # CORRECTED: Use temperature difference (T - T_ref) instead of absolute temperature
    for t in range(1, n):
        dT_current = T_out_series[t] - T_room      # Temperature difference at current time
        dT_previous = T_out_series[t-1] - T_room   # Temperature difference at previous time

        q_in[t] = (Y0 * dT_current + 
                   Y1 * dT_previous + 
                   Phi * q_in[t-1])
                   
    Q_cooling = q_in * A_surface  # Total cooling load (W)
    T_in = T_room + q_in / h_in if h_in > 0 else np.full_like(q_in, T_room) # Estimated inside surface temperature (°C)
    
    return {'Q_cooling': Q_cooling, 'q_flux': q_in, 'T_inside': T_in}

# =====================================================================
# Constants
# =====================================================================

# Stefan–Boltzmann constant [W m^-2 K^-4]
SIGMA = 5.670374419e-8

# =====================================================================
# Weather Data Loading
# =====================================================================

def load_iwec_data(csv_path, sim_year, sim_month, sim_day):
    """
    Load hourly weather data for a single calendar day from an IWEC-type file.

    The function first attempts to extract records whose timestamp year, month, and
    day exactly match the specified simulation date (sim_year, sim_month, sim_day).
    This corresponds to the case where the simulation year is explicitly represented
    in the IWEC / weather file.

    If no such records are found (e.g. when sim_year is not present in the file
    or sim_year is None), the function falls back to a more relaxed selection
    criterion that matches only by month and day across all years available in the
    weather file. In this fallback mode:

    - All records with the requested (month, day) are collected, irrespective of year.
    - If multiple years are available for that calendar day, the earliest year in
      the dataset is selected and used consistently for the entire simulation day.
    - The original year from the IWEC file is preserved in the returned index; the
      timestamps are not remapped to sim_year. This ensures that the time axis
      remains internally consistent with the IWEC data.

    Parameters
    ----------
    csv_path : str
        Path to the comma-separated weather file. The file must contain a column
        named 'Time' that can be parsed as a pandas datetime and will be used
        as the DataFrame index.
    sim_year : int or None
        Target simulation year. If None, or if the specified year is not present
        in the weather file, the function falls back to month/day matching across
        all years contained in the file.
    sim_month : int
        Target simulation month (1–12).
    sim_day : int
        Target simulation day of month (1–31).

    Returns
    -------
    pandas.DataFrame
        A subset of the input weather data corresponding to one calendar day of
        records. The timestamps are aligned to the start of each hour (e.g. HH:00)
        by flooring any sub-hourly time stamps.

    Raises
    ------
    ValueError
        If no records can be found for the requested month/day in the given file.
    """
    print(f"[Weather] Loading IWEC data from: {csv_path}")
    try:
        df = pd.read_csv(csv_path, parse_dates=['Time'], index_col='Time')
    except Exception as e:
        print(f"[ERROR] Could not read or parse weather file: {e}")
        raise

    weather_day = pd.DataFrame()

    # ------------------------------------------------------------------
    # 1) Attempt an exact year–month–day match if sim_year is provided
    # ------------------------------------------------------------------
    if sim_year is not None:
        try:
            start_date = pd.Timestamp(f"{sim_year}-{sim_month}-{sim_day} 00:00:00")
            end_date = start_date + pd.Timedelta(days=1)
            weather_day = df[(df.index >= start_date) & (df.index < end_date)].copy()
        except Exception as e:
            print(f"[Weather] Exact-year filtering failed ({e}); "
                  f"will attempt month/day-only matching.")
            weather_day = pd.DataFrame()

    # ------------------------------------------------------------------
    # 2) If no exact match, fall back to month/day-only matching
    # ------------------------------------------------------------------
    if weather_day.empty:
        print("[Weather] No records found for the exact simulation year; "
              "falling back to month/day matching across all available years.")

        # Select all rows that match the requested month and day,
        # irrespective of the year encoded in the weather file.
        md_mask = (df.index.month == sim_month) & (df.index.day == sim_day)
        weather_day = df[md_mask].copy()

        if weather_day.empty:
            raise ValueError(
                f"No weather data found for month={sim_month}, day={sim_day} "
                f"in file {csv_path}. Please check the CSV and simulation dates."
            )

        # If multiple years are present for this calendar day, retain only the earliest year.
        unique_dates = sorted(weather_day.index.normalize().unique())
        if len(unique_dates) > 1:
            first_date = unique_dates[0]
            weather_day = weather_day[weather_day.index.normalize() == first_date]
            print(f"[Weather] Multiple years detected for the requested day; "
                  f"using IWEC data from {first_date.date()}.")

        else:
            print(f"[Weather] Using IWEC data from {unique_dates[0].date()}.")

        # Note: in this fallback mode, the year in the index is kept as the IWEC year.
        # It is NOT remapped to sim_year, in order to preserve the temporal structure
        # of the IWEC dataset.

    # ------------------------------------------------------------------
    # 3) Align timestamps to the start of each hour (e.g. HH:00)
    #    and, if sim_year was requested but not present in IWEC,
    #    remap the selected day to sim_year while preserving month/day/hour.
    # ------------------------------------------------------------------
    weather_day.index = weather_day.index.floor('h')  # use lowercase to avoid pandas FutureWarning
    if sim_year is not None:
        try:
            weather_day.index = weather_day.index.map(
                lambda ts: ts.replace(year=sim_year)
            )
        except Exception as e:
            print(f"[Weather] Could not remap IWEC day to sim_year={sim_year}: {e}")

    print(f"[Weather] Successfully loaded {len(weather_day)} hourly records "
          f"for calendar day {weather_day.index[0].date()} "
          f"(index year = {weather_day.index[0].year}).")
    return weather_day

# =====================================================================
# Cache utilities
# =====================================================================

def make_cache_prefix(folder, z_refine_factor, z_refine_max_iters,
                      ground_res, ground_buffer, receiver_offset,
                      rays_per_receiver, batch_size, rng_seed):
    folder_name = os.path.basename(os.path.normpath(folder))
    key = f"{folder_name}|zref={z_refine_factor}|zit={z_refine_max_iters}|gres={ground_res}|gbuf={ground_buffer}|roff={receiver_offset}|rays={rays_per_receiver}|bs={batch_size}|seed={rng_seed}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:10]
    return f"{folder_name}_z{z_refine_factor}_gr{ground_res}_gb{ground_buffer}_ro{receiver_offset}_r{rays_per_receiver}_b{batch_size}_s{rng_seed}_{h}"

def mesh_cache_paths(work_dir, prefix):
    mesh_npz = os.path.join(work_dir, f"{prefix}_mesh.npz")
    rt_npz = os.path.join(work_dir, f"{prefix}_rt.npz")
    meta_npz = os.path.join(work_dir, f"{prefix}_meta.npz")
    building_npz = os.path.join(work_dir, f"{prefix}_building.npz")
    return mesh_npz, rt_npz, meta_npz, building_npz

def save_cache(work_dir, prefix, mesh_all, receivers, normals, face_indices,
               svf, hit_tri_matrix, hit_dist_matrix, local_dirs, rays_vf_weights,
               ground_start, ground_end, building_face_ranges, building_names):
    os.makedirs(work_dir, exist_ok=True)
    mesh_npz, rt_npz, meta_npz, building_npz = mesh_cache_paths(work_dir, prefix)
    np.savez_compressed(mesh_npz, vertices=mesh_all.vertices.astype(np.float64), faces=mesh_all.faces.astype(np.int64))
    np.savez_compressed(rt_npz,
                        receivers=receivers.astype(np.float64), normals=normals.astype(np.float64),
                        face_indices=face_indices.astype(np.int64), svf=svf.astype(np.float64),
                        hit_tri_matrix=hit_tri_matrix.astype(np.int64), hit_dist_matrix=hit_dist_matrix.astype(np.float64),
                        local_dirs=local_dirs.astype(np.float64), rays_vf_weights=rays_vf_weights.astype(np.float64))
    np.savez_compressed(meta_npz, ground_start=np.array([ground_start],dtype=np.int64), ground_end=np.array([ground_end],dtype=np.int64))
    building_data = {
        'names': np.array(building_names, dtype=object),
        'ranges': np.array(building_face_ranges, dtype=object)
    }
    np.savez_compressed(building_npz, **building_data)

def load_cache(work_dir, prefix):
    mesh_npz, rt_npz, meta_npz, building_npz = mesh_cache_paths(work_dir, prefix)
    if not (os.path.exists(mesh_npz) and os.path.exists(rt_npz) and os.path.exists(meta_npz)):
        return None
    m=np.load(mesh_npz); r=np.load(rt_npz); meta=np.load(meta_npz)
    mesh_all=trimesh.Trimesh(vertices=m["vertices"], faces=m["faces"], process=False)
    receivers=r["receivers"]; normals=r["normals"]; face_indices=r["face_indices"]; svf=r["svf"]
    hit_tri_matrix=r["hit_tri_matrix"]; hit_dist_matrix=r["hit_dist_matrix"]; local_dirs=r["local_dirs"]; rays_vf_weights=r["rays_vf_weights"]
    ground_start=int(meta["ground_start"][0]); ground_end=int(meta["ground_end"][0])
    building_face_ranges = []
    building_names = []
    if os.path.exists(building_npz):
        building_data = np.load(building_npz, allow_pickle=True)
        building_names = list(building_data['names'])
        building_face_ranges = list(building_data['ranges'])
    return {"mesh_all":mesh_all,"receivers":receivers,"normals":normals,"face_indices":face_indices,"svf":svf,
            "hit_tri_matrix":hit_tri_matrix,"hit_dist_matrix":hit_dist_matrix,"local_dirs":local_dirs,"rays_vf_weights":rays_vf_weights,
            "ground_start":ground_start,"ground_end":ground_end,"building_face_ranges":building_face_ranges,"building_names":building_names}


# =====================================================================
# Rays and sampling
# =====================================================================

def make_ray_intersector(mesh: trimesh.Trimesh):
    try:
        from trimesh.ray.ray_pyembree import RayMeshIntersector
        return RayMeshIntersector(mesh, scale_to_box=True)
    except Exception:
        from trimesh.ray.ray_triangle import RayMeshIntersector
        return RayMeshIntersector(mesh)

def hemisphere_cosine_directions(n, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    u1 = rng.random(n); u2 = rng.random(n)
    r = np.sqrt(u1); theta = 2.0*np.pi*u2
    x = r*np.cos(theta); y = r*np.sin(theta); z = np.sqrt(np.maximum(0.0, 1.0-u1))
    dirs = np.stack([x,y,z], axis=1)
    pdf = z/np.pi
    return dirs, pdf

def orthonormal_basis(normals):
    n = np.asarray(normals, dtype=np.float64)
    n = n/(np.linalg.norm(n, axis=1, keepdims=True)+1e-12)
    N = n
    a = np.empty_like(n)
    mask = np.abs(n[:,2]) < 0.999
    a[mask] = np.array([0.0,0.0,1.0]); a[~mask] = np.array([1.0,0.0,0.0])
    T = np.cross(a,N); T = T/(np.linalg.norm(T, axis=1, keepdims=True)+1e-12)
    B = np.cross(N,T)
    return T,B,N

def rotate_dirs_to_normals(local_dirs, T, B, N):
    x = local_dirs[:,0][None,:]; y = local_dirs[:,1][None,:]; z = local_dirs[:,2][None]
    return (T[:,None,:]*x[...,None] + B[:,None,:]*y[...,None] + N[:,None,:]*z[...,None])

# =====================================================================
# Geometry prep
# =====================================================================

def refine_mesh_along_z(mesh: trimesh.Trimesh, z_refine_factor=1.0, max_iters=3):
    if z_refine_factor is None or z_refine_factor <= 1.0:
        return mesh
    zmin = mesh.vertices[:,2].min(); zmax = mesh.vertices[:,2].max()
    zrange = max(zmax - zmin, 1e-9); base_thresh = zrange/float(z_refine_factor)
    current = mesh.copy()
    for _ in range(int(max_iters)):
        v = current.vertices; f = current.faces
        original_normals = current.face_normals.copy()
        edges = current.edges_unique
        dz = np.abs(v[edges[:,0],2] - v[edges[:,1],2])
        mask = dz > (0.5*base_thresh)
        if not np.any(mask): break
        edges_to_split = edges[mask]
        midpoints = 0.5*(v[edges_to_split[:,0]] + v[edges_to_split[:,1]])
        new_vidx = np.arange(len(v), len(v)+len(midpoints))
        edge_to_mid = {}
        for k,e in enumerate(edges_to_split):
            a,b = int(e[0]), int(e[1])
            if a>b: a,b=b,a
            edge_to_mid[(a,b)] = int(new_vidx[k])
        new_vertices = np.vstack([v, midpoints])
        face_list=[]; face_to_original=[]
        def get_mid(p,q):
            pp,qq = (p,q) if p<q else (q,p)
            return edge_to_mid.get((pp,qq), -1)
        for face_idx, tri in enumerate(f):
            a,b,c = int(tri[0]), int(tri[1]), int(tri[2])
            m_ab = get_mid(a,b); m_bc=get_mid(b,c); m_ca=get_mid(c,a)
            cnt = (m_ab>=0)+(m_bc>=0)+(m_ca>=0)
            if cnt==0:
                face_list.append([a,b,c]); face_to_original.append(face_idx)
            elif cnt==1:
                if m_ab>=0:
                    face_list.append([a,m_ab,c]); face_list.append([m_ab,b,c])
                elif m_bc>=0:
                    face_list.append([a,b,m_bc]); face_list.append([a,m_bc,c])
                else:
                    face_list.append([a,b,m_ca]); face_list.append([m_ca,b,c])
                face_to_original.extend([face_idx,face_idx])
            elif cnt==2:
                if m_ab<0:
                    face_list.append([a,b,m_bc]); face_list.append([a,m_bc,m_ca]); face_list.append([m_ca,m_bc,c])
                elif m_bc<0:
                    face_list.append([m_ab,b,c]); face_list.append([a,m_ab,m_ca]); face_list.append([m_ab,c,m_ca])
                else:
                    face_list.append([a,m_ab,m_bc]); face_list.append([a,m_bc,c]); face_list.append([m_ab,b,m_bc])
                face_to_original.extend([face_idx,face_idx,face_idx])
            else:
                face_list.append([a,m_ab,m_ca]); face_list.append([m_ab,b,m_bc]); face_list.append([m_ca,m_bc,c]); face_list.append([m_ab,m_bc,m_ca])
                face_to_original.extend([face_idx,face_idx,face_idx,face_idx])
        new_faces = np.asarray(face_list, dtype=np.int64)
        current = trimesh.Trimesh(vertices=new_vertices, faces=new_faces, process=False)
        new_normals = current.face_normals
        face_to_original = np.array(face_to_original)
        for i,orig_idx in enumerate(face_to_original):
            if orig_idx < len(original_normals):
                if np.dot(original_normals[orig_idx], new_normals[i]) < -0.1:
                    current.faces[i] = current.faces[i][[0,2,1]]
        current._cache.clear()
        try: current.fix_normals()
        except Exception: pass
    return current

def load_and_refine_buildings(folder, z_refine_factor=1.0, max_iters=3):
    meshes = []
    building_names = []
    building_face_ranges = []
    current_face_offset = 0

    def _clean_mesh(mesh_obj):
        mesh_obj.remove_unreferenced_vertices()
        try:
            mesh_obj.update_faces(mesh_obj.nondegenerate_faces())
        except Exception:
            mesh_obj.remove_degenerate_faces()
        return mesh_obj
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(".stl"):
            building_name = os.path.splitext(fn)[0]
            path = os.path.join(folder, fn)
            m = trimesh.load(path, force='mesh')
            if isinstance(m, trimesh.Trimesh):
                m = _clean_mesh(m)
                if z_refine_factor > 1.0:
                    m = refine_mesh_along_z(m, z_refine_factor, max_iters)
                num_faces = len(m.faces)
                building_face_ranges.append((current_face_offset, current_face_offset + num_faces, building_name))
                current_face_offset += num_faces
                meshes.append(m)
                building_names.append(building_name)
            elif isinstance(m, trimesh.Scene):
                parts = [g for g in m.dump(concatenate=True)]
                for p in parts:
                    p = _clean_mesh(p)
                    if z_refine_factor > 1.0:
                        p = refine_mesh_along_z(p, z_refine_factor, max_iters)
                    num_faces = len(p.faces)
                    building_face_ranges.append((current_face_offset, current_face_offset + num_faces, building_name))
                    current_face_offset += num_faces
                    meshes.append(p)
                    building_names.append(building_name)
    if len(meshes) == 0:
        raise RuntimeError("No STL meshes found")
    combined_mesh = trimesh.util.concatenate(meshes)
    return combined_mesh, building_face_ranges, building_names

def make_ground_grid(mesh: trimesh.Trimesh, buffer=5.0, resolution=2.0, z=None):
    bounds=mesh.bounds; (minx,miny,minz)=bounds[0]; (maxx,maxy,maxz)=bounds[1]
    minx-=buffer; miny-=buffer; maxx+=buffer; maxy+=buffer
    if z is None: z=minz-0.05
    xs=np.arange(minx, maxx+resolution, resolution)
    ys=np.arange(miny, maxy+resolution, resolution)
    XX,YY=np.meshgrid(xs,ys); ZZ=np.full_like(XX, z, dtype=float)
    nx=XX.shape[1]; ny=XX.shape[0]
    verts=np.column_stack([XX.ravel(), YY.ravel(), ZZ.ravel()])
    faces=[]
    def vid(i,j): return i*nx+j
    for i in range(ny-1):
        for j in range(nx-1):
            v00=vid(i,j); v01=vid(i,j+1); v10=vid(i+1,j); v11=vid(i+1,j+1)
            faces.append([v00,v01,v11]); faces.append([v00,v11,v10])
    ground=trimesh.Trimesh(vertices=verts, faces=np.array(faces,dtype=np.int64), process=False)
    if np.mean(ground.face_normals[:,2])<0: ground.faces=ground.faces[:,::-1]
    return ground

def build_receivers_from_mesh(mesh: trimesh.Trimesh, offset=0.1):
    centers=mesh.triangles_center; normals=mesh.face_normals
    receivers=centers+normals*offset
    face_indices=np.arange(len(mesh.faces), dtype=int)
    return receivers, normals, centers, face_indices

def concatenate_scene_and_ground(scene_mesh, ground_mesh):
    b_faces=len(scene_mesh.faces); g_faces=len(ground_mesh.faces)
    mesh_all=trimesh.util.concatenate([scene_mesh, ground_mesh])
    ground_start=b_faces; ground_end=b_faces+g_faces
    return mesh_all, ground_start, ground_end

# =====================================================================
# Ray casting and weights
# =====================================================================

def compute_svf_and_blocking_batched(mesh_all: trimesh.Trimesh,
                                     receivers, normals,
                                     rays_per_receiver=64,
                                     batch_size=800_000,
                                     rng=None):
    _=make_ray_intersector(mesh_all)
    N=receivers.shape[0]; R=int(rays_per_receiver)
    local_dirs,_=hemisphere_cosine_directions(R, rng=rng)
    T,B,Nn=orthonormal_basis(normals)
    x=local_dirs[:,0][None,:]; y=local_dirs[:,1][None,:]; z=local_dirs[:,2][None,:]
    d_world=(T[:,None,:]*x[...,None] + B[:,None,:]*y[...,None] + Nn[:,None,:]*z[...,None])
    d_world/= (np.linalg.norm(d_world, axis=2, keepdims=True)+1e-12)
    origins=receivers[:,None,:]+d_world*1e-4
    M=N*R
    origins_flat=origins.reshape(M,3).astype(np.float64, copy=False)
    dirs_flat=d_world.reshape(M,3).astype(np.float64, copy=False)
    hit_tri=np.full(M,-1,dtype=np.int64); hit_dist=np.full(M,np.inf,dtype=np.float64)
    start=0
    while start<M:
        end=min(start+batch_size, M)
        o_batch=origins_flat[start:end]; d_batch=dirs_flat[start:end]
        try:
            idx_tri,idx_ray,loc=mesh_all.ray.intersects_id(ray_origins=o_batch, ray_directions=d_batch, multiple_hits=False, return_locations=True)
        except TypeError:
            loc,idx_ray,idx_tri=mesh_all.ray.intersects_location(ray_origins=o_batch, ray_directions=d_batch)
        if len(idx_ray)>0:
            d=np.linalg.norm(loc - o_batch[idx_ray], axis=1)
            hit_tri[start+idx_ray]=idx_tri; hit_dist[start+idx_ray]=d
        start=end
    hit_tri_matrix=hit_tri.reshape(N,R); hit_dist_matrix=hit_dist.reshape(N,R)
    svf=np.mean(hit_tri_matrix<0, axis=1).astype(np.float64)
    return svf, hit_tri_matrix, hit_dist_matrix, local_dirs

def compute_geometric_ray_weights(mesh_all: trimesh.Trimesh,
                                  normals,
                                  svf, hit_tri_matrix, hit_dist_matrix,
                                  local_dirs,
                                  eps=1e-6):
    N,R=hit_tri_matrix.shape
    face_normals=mesh_all.face_normals; tri_areas=mesh_all.area_faces
    T,B,Nn=orthonormal_basis(normals)
    d_world=rotate_dirs_to_normals(local_dirs,T,B,Nn)
    valid=hit_tri_matrix>=0
    f_idx=hit_tri_matrix.copy(); f_idx[~valid]=0
    n_f=face_normals[f_idx]
    cos_term=np.einsum('nij,nij->ni', n_f, -d_world); cos_term=np.clip(cos_term,0.0,1.0)
    area=tri_areas[f_idx]; dist2=np.maximum(hit_dist_matrix**2, eps)
    gi=area*cos_term/dist2; gi[~valid]=0.0
    weights=gi
    sum_w=weights.sum(axis=1, keepdims=True)
    target=(1.0 - svf).reshape(-1,1); target=np.clip(target,0.0,1.0)
    scale=np.zeros_like(target); nz=sum_w>eps
    scale[nz]=target[nz]/sum_w[nz]
    weights*=scale
    return weights

def to_kelvin_vector(T_in):
    T_in=np.asarray(T_in,dtype=np.float64)
    mask=(T_in>=200.0)&(T_in>=200.0) # Corrected a typo: & (T_in<=400.0) to (T_in>=200.0)
    return T_in if np.mean(mask)>=0.9 else T_in+273.15

def compute_longwave_components_per_face(mesh_all: trimesh.Trimesh,
                                         receivers, face_indices,
                                         svf, hit_tri_matrix, rays_vf_weights, # MODIFIED: Pass ray tracing data
                                         sky_longwave=400.0,
                                         emissivity=0.9,
                                         T_faces_K=None,
                                         T_roof_C=28.0, 
                                         T_wall_C=26.0,
                                         T_ground_C=40.0,
                                         ground_start=None,
                                         ground_end=None,
                                         roof_upward_threshold=0.7,
                                         wall_vertical_threshold=0.3):
    F=len(mesh_all.faces); N_recv=receivers.shape[0]
    
    # Create a mapping from each face to its corresponding receiver index
    if N_recv==F and np.all(face_indices==np.arange(F)):
        face_to_recv=np.arange(F)
    else:
        tri_centers=mesh_all.triangles_center
        try:
            tree=cKDTree(receivers); _, face_to_recv =tree.query(tri_centers, k=1)
        except Exception:
            face_to_recv=np.mod(np.arange(F),N_recv) if N_recv > 0 else np.zeros(F, dtype=int)

    if T_faces_K is None:
        n = mesh_all.face_normals
        is_ground = np.zeros(F,dtype=bool)
        if ground_start is not None and ground_end is not None: is_ground[ground_start:ground_end]=True
        nz=n[:,2]
        is_roof=(~is_ground) & (nz>=roof_upward_threshold)
        is_wall=(~is_ground) & (np.abs(nz)<=wall_vertical_threshold)
        T_faces=np.empty(F,dtype=np.float64)
        T_faces[is_ground]=T_ground_C+273.15
        T_faces[is_roof]=T_roof_C+273.15
        T_faces[is_wall]=T_wall_C+273.15
        T_faces[~(is_ground|is_roof|is_wall)]=T_wall_C+273.15
    else:
        T_faces=to_kelvin_vector(T_faces_K)

    # 1. Emitted LW from each surface (E_faces)
    E_faces = emissivity * SIGMA * T_faces**4

    # 2. Incident LW from the sky
    SVF_faces = svf[face_to_recv]
    LW_sky_down  = SVF_faces * sky_longwave
    
    # 3. Incident LW from other surfaces (LW_surf_down)
    # This is the precise calculation requested by the user, using the specific temperature
    # of each facet hit by rays.
    
    # A mask for valid hits (ray hit a surface)
    valid_hits = hit_tri_matrix >= 0
    
    # Get the emitted energy of the specific face hit by each ray.
    # Where the hit was invalid (hit the sky), the index will be bad, but we zero it out later.
    E_hit_faces = E_faces[hit_tri_matrix]
    
    # Calculate the energy contribution for each ray of each receiver
    energy_contributions = rays_vf_weights * E_hit_faces
    energy_contributions[~valid_hits] = 0.0 # Zero out contributions from rays that hit the sky
    
    # Sum the energy contributions for each receiver across all its rays
    lw_incident_per_receiver = np.sum(energy_contributions, axis=1)
    
    # Map the per-receiver incident energy back to the per-face array
    LW_surf_down = lw_incident_per_receiver[face_to_recv]

    # For debugging: print the values on the first run
    if np.isclose(np.mean(T_faces_K), 298.15):
        print(f"[LW Model Debug] Sky LW input: {sky_longwave:.2f} W/m^2")
        print(f"[LW Model Debug] Avg LW from surfaces (calculated precisely): {np.mean(LW_surf_down[SVF_faces < 0.99]):.2f} W/m^2")
    
    # 4. Net LW radiation
    LW_net = (LW_sky_down + LW_surf_down) - E_faces
    print("LW_sky_down, LW_surf_down",max(LW_sky_down),max(LW_surf_down),max(LW_sky_down + LW_surf_down))
    return LW_sky_down, LW_surf_down, E_faces, LW_net, T_faces

def compute_shortwave_components_per_face(mesh_all: trimesh.Trimesh,
                                          svf,
                                          dni, dhi,
                                          when_local_sgt,
                                          lat=1.3521, lon=103.8198, alt=15.0,
                                          receivers=None,
                                          use_sun_shadow=True,
                                          batch_size=200000):
    
    if dni < 1.0 and dhi < 1.0:
        F = len(mesh_all.faces)
        zeros = np.zeros(F, dtype=np.float64)
        return zeros, zeros, zeros, {"zenith_deg": 90.0, "azimuth_deg": 0.0}, np.pi / 2

    assert isinstance(when_local_sgt,(pd.Timestamp,dt.datetime))
    if isinstance(when_local_sgt, dt.datetime): 
        when_local_sgt = pd.Timestamp(when_local_sgt, tz='Asia/Singapore') if when_local_sgt.tzinfo is None else pd.Timestamp(when_local_sgt)
    when_local_sgt = when_local_sgt.tz_localize('Asia/Singapore') if when_local_sgt.tz is None else when_local_sgt.tz_convert('Asia/Singapore')
    times_local = pd.DatetimeIndex([when_local_sgt])

    solpos = pvlib.solarposition.spa_python(times_local, latitude=lat, longitude=lon, altitude=alt, how='numpy')
    zen_deg=float(solpos['apparent_zenith'].values[0]); azi_deg=float(solpos['azimuth'].values[0])
    zen=np.deg2rad(zen_deg); azi=np.deg2rad(azi_deg)
    s_vec=np.array([np.sin(zen)*np.sin(azi), np.sin(zen)*np.cos(azi), np.cos(zen)],dtype=np.float64)

    n=mesh_all.face_normals; centers=mesh_all.triangles_center; F=len(n)
    cos_inc=np.einsum('ij,j->i', n, s_vec); cos_inc=np.clip(cos_inc,0.0,1.0)

    if use_sun_shadow and dni>1.0 and cos_inc.max()>0:
        _=make_ray_intersector(mesh_all)
        origins=centers+n*1e-4; dirs=np.repeat(s_vec[None,:],F,axis=0)
        sunlit=np.ones(F,dtype=bool); start=0
        while start<F:
            end=min(start+batch_size,F)
            o_batch=origins[start:end]; d_batch=dirs[start:end]
            try:
                idx_tri,idx_ray,loc=mesh_all.ray.intersects_id(ray_origins=o_batch, ray_directions=d_batch, multiple_hits=False, return_locations=True)
            except TypeError:
                loc,idx_ray,idx_tri=mesh_all.ray.intersects_location(ray_origins=o_batch, ray_directions=d_batch)
            if len(idx_ray)>0:
                hit_global=start+idx_ray; sunlit[hit_global]=False
            start=end
        sun_mask=sunlit
    else:
        sun_mask=cos_inc>0

    SW_direct = dni * cos_inc * sun_mask

    tilt_deg=np.degrees(np.arccos(np.clip(n[:,2],-1.0,1.0)))
    az_deg_surf=(np.degrees(np.arctan2(n[:,0],n[:,1]))+360.0)%360.0
    dni_extra=float(pvlib.irradiance.get_extra_radiation(times_local).values[0])
    am_rel=float(pvlib.atmosphere.get_relative_airmass(zen_deg))
    E_d_perez=pvlib.irradiance.perez(surface_tilt=tilt_deg, surface_azimuth=az_deg_surf,
                                     dhi=dhi, dni=dni, dni_extra=dni_extra,
                                     solar_zenith=zen_deg, solar_azimuth=azi_deg,
                                     airmass=am_rel, model='allsitescomposite1990',
                                     return_components=False)
    SVF_faces = svf
    if SVF_faces.shape[0] != F:
        if receivers is None:
            SVF_faces = np.full(F, float(np.nanmean(svf)))
        else:
            tree=cKDTree(receivers); _, nn=tree.query(centers, k=1)
            SVF_faces = svf[nn]
    SW_diffuse = SVF_faces * E_d_perez
    SW_total = SW_direct + SW_diffuse
    return SW_direct, SW_diffuse, SW_total, {"zenith_deg": zen_deg, "azimuth_deg": azi_deg}, float(zen)


# =====================================================================
# Visualization and Interpolation
# =====================================================================

def _cmap_mesh(mesh, scalars, title, cmap_name='plasma',
               vmin=None, vmax=None, filename=None, base_color='darkgray'):
    """
    Helper to create a vedo Mesh with per-cell scalar colouring.

    The colormap range is determined only from finite (non-NaN, non-inf) values.
    Faces whose scalar value is NaN are left with the mesh's base colour, which
    is set to a neutral dark gray by default. This is useful, for example, to
    display buildings or ground regions without MRT/PET data as neutral geometry.
    """
    # Create a mesh, initially set to a dark gray base color.
    vmesh = Mesh([mesh.vertices, mesh.faces]).c(base_color)

    vals = scalars.astype(float)

    # Determine the color scale using only finite values.
    valid = np.isfinite(vals)
    if not np.any(valid):
        # If no valid values exist, provide a dummy range to avoid errors.
        vmin_ = 0.0
        vmax_ = 1.0
    elif vmin is None or vmax is None:
        valid_vals = vals[valid]
        if np.all(valid_vals == valid_vals[0]):
            vmin_ = float(valid_vals[0] - 0.5)
            vmax_ = float(valid_vals[0] + 0.5)
        else:
            vmin_ = float(np.nanpercentile(valid_vals, 5))
            vmax_ = float(np.nanpercentile(valid_vals, 95))
            if vmin_ == vmax_:
                vmin_ -= 1.0
                vmax_ += 1.0
    else:
        vmin_, vmax_ = float(vmin), float(vmax)

    # Apply colormap: only non-NaN cells will be colored;
    # NaN values will retain the base_color.
    vmesh.cmap(
        cmap_name,
        vals,
        on="cells",
        vmin=vmin_,
        vmax=vmax_,
    ).add_scalarbar3d(title=title)

    if filename:
        write(vmesh, filename)

    return vmesh


def rotate_points(x, y, angle_deg):
    """Rotate 2D coordinates by angle_deg (counter-clockwise positive)."""
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    x = np.asarray(x); y = np.asarray(y)
    x_rot = x * ca - y * sa
    y_rot = x * sa + y * ca
    return x_rot, y_rot


# =====================================================================
# CFD-specific functions
# =====================================================================

def load_and_combine_meshes_cfd(directory, building_face_ranges_out):
    """Load all STL files in *directory* and concatenate them into one mesh."""
    stl_files = sorted(glob.glob(os.path.join(directory, "*.stl")))
    if not stl_files:
        raise FileNotFoundError(f"No STL files found in {directory!r}")

    def _clean_mesh(mesh_obj):
        mesh_obj.remove_unreferenced_vertices()
        try:
            mesh_obj.update_faces(mesh_obj.nondegenerate_faces())
        except Exception:
            mesh_obj.remove_degenerate_faces()
        return mesh_obj

    meshes = []
    building_face_ranges_out.clear()
    current_offset = 0
    for stl_path in stl_files:
        m = trimesh.load(stl_path)
        building_name = os.path.splitext(os.path.basename(stl_path))[0]
        if isinstance(m, trimesh.Trimesh): parts = [m]
        else: parts = list(m.dump(concatenate=True))
        for p in parts:
            p = _clean_mesh(p)
            if len(p.faces) == 0: continue
            building_face_ranges_out.append((current_offset, current_offset + len(p.faces), building_name))
            current_offset += len(p.faces)
            meshes.append(p)
    if not meshes: raise RuntimeError("No valid mesh faces found in STL files.")
    return trimesh.util.concatenate(meshes)

def compute_reachable_fluid_mask(solid_mask):
    """Flood-fill from domain boundaries to identify fluid cells reachable from outside."""
    ny, nx = solid_mask.shape
    fluid_mask = ~solid_mask
    reachable = np.zeros_like(fluid_mask, dtype=bool)
    q = deque()
    for i in range(nx):
        if fluid_mask[0, i]: reachable[0, i] = True; q.append((0, i))
        if fluid_mask[ny - 1, i]: reachable[ny - 1, i] = True; q.append((ny - 1, i))
    for j in range(ny):
        if fluid_mask[j, 0]: reachable[j, 0] = True; q.append((j, 0))
        if fluid_mask[j, nx - 1]: reachable[j, nx - 1] = True; q.append((j, nx - 1))
    while q:
        j, i = q.popleft()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            jj, ii = j + dj, i + di
            if 0 <= jj < ny and 0 <= ii < nx and fluid_mask[jj, ii] and not reachable[jj, ii]:
                reachable[jj, ii] = True
                q.append((jj, ii))
    return reachable

def solve_potential_flow(fluid_mask, x_coords, U):
    """Solve ∇²φ = 0 on a 2D grid with Dirichlet boundary φ = U (x - xmin)."""
    ny, nx = fluid_mask.shape
    N = fluid_mask.sum()
    if N == 0: return np.full_like(fluid_mask, np.nan, dtype=float)
    idmap = -np.ones_like(fluid_mask, dtype=int); idmap[fluid_mask] = np.arange(N)
    rows, cols, data, b = [], [], [], np.zeros(N)
    xmin = float(x_coords.min())
    for j in range(ny):
        for i in range(nx):
            if not fluid_mask[j, i]: continue
            p = idmap[j, i]
            if i == 0 or i == nx - 1 or j == 0 or j == ny - 1:
                rows.append(p); cols.append(p); data.append(1.0)
                b[p] = U * (x_coords[i] - xmin)
                continue
            diag = 0.0
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jj, ii = j + dj, i + di
                if 0 <= jj < ny and 0 <= ii < nx and fluid_mask[jj, ii]:
                    q = idmap[jj, ii]
                    rows.append(p); cols.append(q); data.append(1.0)
                    diag -= 1.0
            rows.append(p); cols.append(p); data.append(diag)
    A = sparse.csr_matrix((data, (rows, cols)), shape=(N, N))
    phi_vec = spsolve(A, b)
    phi_grid = np.full_like(fluid_mask, np.nan, dtype=float); phi_grid[fluid_mask] = phi_vec
    return phi_grid

def velocity_from_potential(phi_grid, fluid_mask, dx, dy):
    """Compute velocity components u = ∂φ/∂x, v = ∂φ/∂y via finite differences."""
    ny, nx = phi_grid.shape
    u, v = np.zeros_like(phi_grid), np.zeros_like(phi_grid)
    for j in range(ny):
        for i in range(nx):
            if not fluid_mask[j, i]: continue
            if 0 < i < nx - 1 and fluid_mask[j, i - 1] and fluid_mask[j, i + 1]: u[j, i] = (phi_grid[j, i + 1] - phi_grid[j, i - 1]) / (2.0 * dx)
            elif i < nx - 1 and fluid_mask[j, i + 1]: u[j, i] = (phi_grid[j, i + 1] - phi_grid[j, i]) / dx
            elif i > 0 and fluid_mask[j, i - 1]: u[j, i] = (phi_grid[j, i] - phi_grid[j, i - 1]) / dx
            if 0 < j < ny - 1 and fluid_mask[j - 1, i] and fluid_mask[j + 1, i]: v[j, i] = (phi_grid[j + 1, i] - phi_grid[j - 1, i]) / (2.0 * dy)
            elif j < ny - 1 and fluid_mask[j + 1, i]: v[j, i] = (phi_grid[j + 1, i] - phi_grid[j, i]) / dy
            elif j > 0 and fluid_mask[j - 1, i]: v[j, i] = (phi_grid[j, i] - phi_grid[j - 1, i]) / dy
    return u, v

def apply_physical_speed_limits(speed, fluid_mask, U_max):
    """Clip speed to [0, U_max] and set non-fluid cells to NaN."""
    s = np.clip(speed, 0.0, U_max)
    s[~fluid_mask] = np.nan
    return s

def tropical_air_model(speed, T, RH, radiation=800, alpha_evap=0.8, alpha_mix=0.3, beta_vapor=3.0):
    """
    Compact tropical air temperature-humidity model with wind speed effects.
    
    Physical mechanisms: evaporative cooling, boundary layer mixing, and radiative effects.
    Optimized for tropical maritime/monsoon climates (20-35°C, 60-95% RH).
    
    Args:
        speed: Wind speed (m/s) - scalar or array
        T: Air temperature (°C) - scalar or array
        RH: Relative humidity (%) - scalar or array
        radiation: Solar radiation (W/m²), default 800, use 0 for nighttime - scalar or array
        alpha_evap: Evaporative cooling coefficient (default 0.8)
        alpha_mix: Boundary layer mixing coefficient (default 0.3)
        beta_vapor: Vapor removal coefficient (default 3.0)
    
    Returns:
        T_adj: Adjusted temperature (°C) - scalar or array (same shape as inputs)
        RH_adj: Adjusted relative humidity (%) - scalar or array (same shape as inputs)
    
    References:
        - Stull, R.B. (1988). An Introduction to Boundary Layer Meteorology. 
          Kluwer Academic Publishers, Dordrecht, Netherlands. 666 pp.
          https://doi.org/10.1007/978-94-009-3027-8
          
        - Fairall, C.W., Bradley, E.F., Hare, J.E., Grachev, A.A., and Edson, J.B. (2003). 
          Bulk parameterization of air-sea fluxes: Updates and verification for the 
          COARE algorithm. Journal of Climate, 16(4), 571-591.
          https://doi.org/10.1175/1520-0442(2003)016<0571:BPOASF>2.0.CO;2
          
        - Meyers, G., Phillips, H., Smith, N., and Sprintall, J. (1986).
          Space-time patterns of hydrographic variables in the tropical Pacific Ocean.
          Progress in Oceanography, 17(3-4), 285-325.
          https://doi.org/10.1016/0079-6611(86)90042-3
    
    Examples:
        >>> # Single point calculation
        >>> T_adj, RH_adj = tropical_air_model(5.0, 30.0, 75.0)
        >>> print(f"T={T_adj:.2f}°C, RH={RH_adj:.1f}%")
        
        >>> # Multiple wind speeds
        >>> speeds = np.array([0, 5, 10, 15])
        >>> T_adj, RH_adj = tropical_air_model(speeds, 30.0, 75.0)
        
        >>> # Multiple temperatures and humidities
        >>> temps = np.array([28, 30, 32, 34])
        >>> RHs = np.array([70, 75, 80, 85])
        >>> T_adj, RH_adj = tropical_air_model(5.0, temps, RHs)
        
        >>> # Full 2D array (all inputs as arrays)
        >>> speeds = np.array([0, 5, 10])
        >>> temps = np.array([28, 30, 32])
        >>> RHs = np.array([70, 75, 80])
        >>> T_adj, RH_adj = tropical_air_model(speeds, temps, RHs)
        
        >>> # Nighttime calculation
        >>> T_night, RH_night = tropical_air_model(5.0, 28.0, 85.0, radiation=0)
    """
    # Vectorize and validate inputs
    speed, T, RH, radiation = [np.asarray(x, dtype=float) for x in [speed, T, RH, radiation]]
    speed = np.clip(np.nan_to_num(speed), 0, 50)
    RH = np.clip(RH, 0, 100)
    
    # Broadcast all arrays to compatible shape
    speed, T, RH, radiation = np.broadcast_arrays(speed, T, RH, radiation)
    
    # Temperature adjustment
    humidity_factor = 1.0 - (RH / 100.0) ** 1.5
    evap_cooling = alpha_evap * np.sqrt(speed) * humidity_factor
    mix_cooling = alpha_mix * np.log1p(speed) * np.where(radiation > 50, 1.0, 0.1)
    rad_heating = radiation * 0.00015 / (1.0 + 0.1 * speed)
    longwave_cooling = np.where(radiation > 50, 0, 0.3)
    
    delta_T = -(evap_cooling + mix_cooling + longwave_cooling) + rad_heating
    T_adj = T + delta_T
    
    # Humidity adjustment (Magnus-Tetens formula)
    e_sat_old = 6.112 * np.exp(17.67 * T / (T + 243.5))
    e_sat_new = 6.112 * np.exp(17.67 * T_adj / (T_adj + 243.5))
    vapor_removal = np.clip(beta_vapor * np.log1p(speed) * (1 - RH / 120), 0, 25) / 100
    
    e_actual = (RH / 100) * e_sat_old * (1 - vapor_removal)
    RH_adj = np.clip(100 * e_actual / e_sat_new, 5, 100)
    
    # Return scalar if all inputs were scalar
    if T_adj.ndim == 0:
        return float(T_adj), float(RH_adj)
    
    return T_adj, RH_adj

def compute_pet_series(tdb_2m, tr_2m, v_2m, rh_2m,
                       met, clo, age, sex, height, weight, p_atm,
                       n_debug=5):
    def _pet_value(x):
        """Robustly extract a float PET value from pythermalcomfort output."""
        try:
            if hasattr(x, "pet"):
                return float(x.pet)
            if hasattr(x, "PET"):
                return float(x.PET)
            return float(x)
        except Exception:
            return float(np.asarray(x).astype(float))

    pet_values = []

    common_kwargs = dict(
        met=met,
        clo=clo,
        age=age,
        sex=sex,
        height=height,
        weight=weight,
        p_atm=p_atm,
    )

    print("\n--- Debugging first 5 PET calculations ---")
    for i, (tdb, tr, v, rh) in enumerate(zip(tdb_2m, tr_2m, v_2m, rh_2m)):
        # Enforce a minimum wind speed of 0.1 m/s for PET solver stability, as the model is sensitive to still air (v=0).
        v_stable = max(v, 0.1)
        
        pet = pet_steady(
            tdb=tdb,
            tr=tr,
            v=v_stable,
            rh=rh,
            **common_kwargs
        )
        pet_val = _pet_value(pet)

        if i < n_debug:
            print(f"Point {i}:")
            print(f"  Inputs: tdb={tdb:.2f}, tr={tr:.2f}, v={v:.2f} (used: {v_stable:.2f}), rh={rh:.2f}")
            print(f"  Output: PET={pet_val:.2f}")

        pet_values.append(pet_val)
    
    print("----------------------------------------\n")
    return np.array(pet_values, dtype=float)

def compute_facet_fields_from_slices(combined_mesh, slice_sample_data, ground_start_index):
    """Interpolate facet U/T/H from multi-height slice fields."""
    n_faces = len(combined_mesh.faces)
    centers = combined_mesh.triangles_center
    facet_speed, facet_temp, facet_rh = np.zeros(n_faces), np.zeros(n_faces), np.zeros(n_faces)
    
    # Process building faces (non-ground) using vertical interpolation
    building_face_indices = np.arange(0, ground_start_index)
    for i in building_face_indices:
        cx, cy, cz = centers[i]
        zs, s_vals, t_vals, h_vals = [], [], [], []
        for d in slice_sample_data:
            if d.get("tree") is None: continue
            dist, idx = d["tree"].query([cx, cy])
            zs.append(d["z"]); s_vals.append(d["speed"][idx]); t_vals.append(d["temp"][idx]); h_vals.append(d["rh"][idx])
        if not zs: continue
        zs, s_vals, t_vals, h_vals = np.array(zs), np.array(s_vals), np.array(t_vals), np.array(h_vals)
        order = np.argsort(zs)
        facet_speed[i] = float(np.interp(cz, zs[order], s_vals[order]))
        facet_temp[i] = float(np.interp(cz, zs[order], t_vals[order]))
        facet_rh[i] = float(np.interp(cz, zs[order], h_vals[order]))

    # Process ground faces using vertical interpolation/extrapolation
    ground_face_indices = np.arange(ground_start_index, n_faces)
    for i in ground_face_indices:
        cx, cy, cz = centers[i] # cz will be ~0 for ground
        zs, s_vals, t_vals, h_vals = [], [], [], []
        for d in slice_sample_data:
            if d.get("tree") is None: continue
            # Query for the closest point in the current slice's KDTree
            dist, idx = d["tree"].query([cx, cy])
            zs.append(d["z"])
            s_vals.append(d["speed"][idx])
            t_vals.append(d["temp"][idx])
            h_vals.append(d["rh"][idx])
        
        if not zs:
            # Fallback if no valid slice data is found
            facet_speed[i] = 0.0 # Default to no wind
            facet_temp[i] = 25.0 # Default temp
            facet_rh[i] = 70.0 # Default RH
            continue

        zs, s_vals, t_vals, h_vals = np.array(zs), np.array(s_vals), np.array(t_vals), np.array(h_vals)
        order = np.argsort(zs) # Ensure arrays are sorted by z for interp
        
        # Interpolate/extrapolate using cz (which is ~0 for ground)
        facet_speed[i] = float(np.interp(cz, zs[order], s_vals[order]))
        facet_temp[i] = float(np.interp(cz, zs[order], t_vals[order]))
        facet_rh[i] = float(np.interp(cz, zs[order], h_vals[order]))
    
    print("    Applied vertical interpolation/extrapolation to ground plane.")
    
    return facet_speed, facet_temp, facet_rh

# =====================================================================
# Main Coupled Simulation
# =====================================================================

def main_coupled_run(
    # General Simulation Settings
    sim_year=2025,              # Simulation year for weather data (e.g., 2025)
    sim_month=10,               # Simulation month for weather data (1-12)
    sim_day=4,                  # Simulation day for weather data (1-31)
    dt_hours: float = 1.0,      # Timestep duration in hours for simulation loop
    common_stl_dir=".",         # Directory containing building geometry STL files
    weather_csv_path="SGP_Singapore_486980_IWEC.csv", # Path to IWEC weather data CSV file
    work_dir=None,              # Working directory for cache files (e.g., ray-tracing cache)
    output_dir=None,            # Output directory for results (screenshots, VTK files, etc.)
    # Weather Overrides (set to a float/int to override CSV data, or None to use CSV)
    wind_dir_override=None,     # Override for wind direction (at 10m height, degrees from North)
    wind_speed_override=None,   # Override for wind speed (at 10m height, m/s)
    air_temp_override=None,     # Override for air temperature (at 2m height, °C)
    rh_override=None,           # Override for relative humidity (at 2m height, %)
    dni_override=None,          # Override for Direct Normal Irradiance (W/m²)
    dhi_override=None,          # Override for Diffuse Horizontal Irradiance (W/m²)
    sky_lw_override=None,       # Override for Horizontal Infrared Radiation Intensity (W/m²)
    # CFD Parameters
    cfd_voxel_pitch=4.0,        # Voxel grid resolution for CFD (m)
    cfd_buffer_ratio=0.10,      # Buffer ratio around buildings for CFD domain (dimensionless)
    cfd_log_z0=0.5,             # Roughness length for logarithmic wind profile in CFD (m)
    # Radiation Model Parameters
    rad_rays_per_receiver=64,   # Number of rays cast per receiver point for sky view factor calculation
    rad_batch_size=500_000,     # Batch size for ray-tracing intersections to manage memory
    rad_rng_seed=12345,         # Random number generator seed for reproducible ray-tracing
    rad_receiver_offset=0.1,    # Offset distance of receiver points from surface (m)
    rad_ground_buffer=20.0,     # Buffer distance around building footprint for ground mesh (m)
    rad_ground_res=25.0,        # Resolution of ground mesh grid (m)
    rad_z_refine_factor=1,      # Factor for mesh refinement along Z-axis (dimensionless)
    rad_z_refine_max_iters=3,   # Maximum iterations for Z-axis mesh refinement
    rad_emissivity_ground=0.95, # Longwave emissivity of ground surface (dimensionless)
    rad_emissivity_wall=0.92,   # Longwave emissivity of building wall surfaces (dimensionless)
    rad_emissivity_roof=0.9,    # Longwave emissivity of building roof surfaces (dimensionless)
    rad_albedo_ground=0.2,      # Shortwave albedo of ground surface (dimensionless)
    rad_albedo_wall=0.4,        # Shortwave albedo of building wall surfaces (dimensionless)
    rad_albedo_roof=0.6,        # Shortwave albedo of building roof surfaces (dimensionless)
    rad_thickness_ground=0.5,   # Thermal thickness of ground layer for heat capacity (m)
    rad_thickness_wall=0.2,     # Thermal thickness of wall layer for heat capacity (m)
    rad_thickness_roof=0.15,    # Thermal thickness of roof layer for heat capacity (m)
    rad_k_ground=None,          # Thermal conductivity of ground layer (W/m·K) [optional]
    rad_k_wall=None,            # Thermal conductivity of wall layer (W/m·K) [optional]
    rad_k_roof=None,            # Thermal conductivity of roof layer (W/m·K) [optional]
    rad_rho_ground=None,        # Density of ground layer (kg/m³) [optional]
    rad_rho_wall=None,          # Density of wall layer (kg/m³) [optional]
    rad_rho_roof=None,          # Density of roof layer (kg/m³) [optional]
    rad_cp_ground=None,         # Specific heat of ground layer (J/kg·K) [optional]
    rad_cp_wall=None,           # Specific heat of wall layer (J/kg·K) [optional]
    rad_cp_roof=None,           # Specific heat of roof layer (J/kg·K) [optional]
    rad_alpha_k=0.7,            # Shortwave absorption coefficient of skin (dimensionless)
    rad_eps_p=0.96,             # Longwave emissivity of human body surface (dimensionless)
    rad_sky_longwave_offset=0.0,# Offset to adjust sky longwave radiation (W/m²)
    rad_C_face_roof=0.5e6,      # Volumetric heat capacity of roof (J/m³K) - for thermal mass
    rad_C_face_wall=0.5e6,      # Volumetric heat capacity of wall (J/m³K) - for thermal mass
    rad_C_face_ground=0.5e6,    # Volumetric heat capacity of ground (J/m³K) - for thermal mass
    rad_lat=1.3521,             # Latitude of simulation location (degrees)
    rad_lon=103.8198,           # Longitude of simulation location (degrees)
    rad_alt=15.0,               # Altitude of simulation location (m)
    rad_H_default=15.0,         # Default convection coefficient (W/m²K) for surfaces if CFD is not run
    # Building Energy Model Parameters
    be_concrete_k=1.7,          # Concrete thermal conductivity (W/(m·K))
    be_concrete_l=0.2,          # Concrete thickness (m)
    be_concrete_rho=2200,       # Concrete density (kg/m³)
    be_concrete_cp=880,         # Concrete specific heat capacity (J/(kg·K))
    be_h_in=8.0,                # Interior convective heat transfer coefficient (W/(m²·K))
    be_t_room=25.0,             # Constant interior room temperature for energy calculations (°C)
    # PET Comfort Model Parameters
    pet_met=1.7,                # Metabolic rate for PET calculation (met)
    pet_clo=0.45,               # Clothing insulation for PET calculation (clo)
    pet_age=35,                 # Age of occupant for PET calculation (years)
    pet_sex="male",             # Sex of occupant for PET calculation ("male" or "female")
    pet_height=1.70,            # Height of occupant for PET calculation (m)
    pet_weight=65,              # Weight of occupant for PET calculation (kg)
    pet_p_atm=1010,             # Atmospheric pressure for PET calculation (hPa)
    # Execution Flags
    run_radiation=True,         # Flag to enable/disable radiation model execution
    run_cfd=True,               # Flag to enable/disable CFD model execution
    vedo_display_mode='off', # VEDO display mode: 'interactive', 'non-interactive', or 'off'
):
    # Ensure offscreen rendering when display mode is 'off' to avoid GUI/X dependency; still allows saving outputs.
    if vedo_display_mode == 'off':
        try:
            import os
            os.environ.setdefault("DISPLAY", "")
            os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
            os.environ.setdefault("VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN", "1")
        except Exception:
            pass
    try:
        import vedo
        vedo.settings.offscreen = (vedo_display_mode == 'off')
    except Exception:
        pass
    print("\n" + "#"*80)
    print("STARTING COUPLED URBAN MICROCLIMATE SIMULATION (TIME-STEPPED)")
    print("#"*80 + "\n")
    total_start_time = time.perf_counter()

    setup_start = time.perf_counter()
    print("[PHASE 1] Loading Data and Initializing Models")
    if work_dir is None: work_dir = os.path.join(os.getcwd(), "rt_cache")
    if output_dir is None: output_dir = os.path.join(os.getcwd(), "coupled_output")
    screenshot_dir = os.path.join(output_dir, "screenshots")
    vtk_dir = os.path.join(output_dir, "vtk_files")
    os.makedirs(work_dir, exist_ok=True); os.makedirs(output_dir, exist_ok=True); os.makedirs(screenshot_dir, exist_ok=True); os.makedirs(vtk_dir, exist_ok=True)
    
    weather_data = load_iwec_data(weather_csv_path, sim_year, sim_month, sim_day)

    rng = np.random.default_rng(rad_rng_seed)
    prefix = make_cache_prefix(common_stl_dir, rad_z_refine_factor, rad_z_refine_max_iters, rad_ground_res, rad_ground_buffer, rad_receiver_offset, rad_rays_per_receiver, rad_batch_size, rad_rng_seed)
    cache = load_cache(work_dir, prefix)
    if cache is not None:
        mesh_all=cache["mesh_all"]; receivers=cache["receivers"]; normals=cache["normals"]; face_indices=cache["face_indices"]; svf=cache["svf"]
        hit_tri_matrix=cache["hit_tri_matrix"]; hit_dist_matrix=cache["hit_dist_matrix"]; local_dirs=cache["local_dirs"]; rays_vf_weights=cache["rays_vf_weights"]
        ground_start=cache["ground_start"]; ground_end=cache["ground_end"]
        building_face_ranges=cache.get("building_face_ranges", []); building_names=cache.get("building_names", [])
        print(f"[Cache] Loaded Radiation geometry: {prefix}")
    else:
        print("[Cache] No radiation cache found, processing geometry...")
        scene_mesh, building_face_ranges, building_names = load_and_refine_buildings(common_stl_dir, z_refine_factor=rad_z_refine_factor, max_iters=rad_z_refine_max_iters)
        ground_mesh=make_ground_grid(scene_mesh, buffer=rad_ground_buffer, resolution=rad_ground_res, z=None)
        mesh_all, ground_start, ground_end = concatenate_scene_and_ground(scene_mesh, ground_mesh)
        receivers, normals, centers, face_indices = build_receivers_from_mesh(mesh_all, offset=rad_receiver_offset)
        svf, hit_tri_matrix, hit_dist_matrix, local_dirs = compute_svf_and_blocking_batched(mesh_all, receivers, normals, rays_per_receiver=rad_rays_per_receiver, batch_size=rad_batch_size, rng=rng)
        rays_vf_weights = compute_geometric_ray_weights(mesh_all=mesh_all, normals=normals, svf=svf, hit_tri_matrix=hit_tri_matrix, hit_dist_matrix=hit_dist_matrix, local_dirs=local_dirs)
        save_cache(work_dir, prefix, mesh_all, receivers, normals, face_indices, svf, hit_tri_matrix, hit_dist_matrix, local_dirs, rays_vf_weights, ground_start, ground_end, building_face_ranges, building_names)
        print(f"[Cache] Saved Radiation geometry: {prefix}")
    
    
    cfd_building_face_ranges = []
    cfd_combined_mesh = load_and_combine_meshes_cfd(common_stl_dir, cfd_building_face_ranges)
    z_top = mesh_all.bounds[1, 2]
    slice_heights = [2.0, 0.5, 10.0, 20.0, z_top]
    tri_centers_all = mesh_all.triangles_center
    building_metadata = []
    for start, end, name in building_face_ranges:
        idx = np.arange(start, end, dtype=int)
        centroid = (
            tri_centers_all[idx].mean(axis=0).tolist()
            if idx.size > 0
            else [0.0, 0.0, 0.0]
        )
        building_metadata.append({"name": name, "indices": idx, "centroid": centroid})
    analysis_summary = {
        "building_metrics": {
            meta["name"]: {
                "max_surface_temp_c": float("-inf"),
                "max_surface_temp_time": "",
                "max_surface_wind_ms": float("-inf"),
                "max_surface_wind_time": "",
                "max_surface_temp_location": None,
            }
            for meta in building_metadata
        },
        "ground_hotspots": [],
        "cooling_energy": {
            "per_building_kWh": {meta["name"]: 0.0 for meta in building_metadata},
            "per_building_max_hourly_kw": {meta["name"]: {"value": 0.0, "time": ""} for meta in building_metadata},
            "total_kWh": 0.0,
        },
        "metadata": {
            "simulation_year": sim_year,
            "simulation_date": f"{sim_year:04d}-{sim_month:02d}-{sim_day:02d}",
        },
    }
    analysis_summary_path = os.path.join(output_dir, "analysis_metrics.json")
    def _nearest_buildings(pt2, metadata, top_k=2):
        try:
            pt = np.array(pt2, dtype=float)
            scores = []
            for meta in metadata:
                c = np.array(meta.get("centroid", [0, 0]), dtype=float)
                dist = float(np.linalg.norm(pt - c[:2]))
                scores.append((meta["name"], dist))
            scores.sort(key=lambda x: x[1])
            return [s[0] for s in scores[:top_k]]
        except Exception:
            return []
    
    F=len(mesh_all.faces)
    T_prev = np.full(F, 25.0 + 273.15, dtype=np.float64)

    # Initialize per-face physical properties based on surface type
    n = mesh_all.face_normals
    is_ground = np.zeros(F, dtype=bool)
    if ground_start is not None and ground_end is not None:
        is_ground[ground_start:ground_end] = True
    
    roof_upward_threshold=0.7
    wall_vertical_threshold=0.3
    nz = n[:,2]
    is_roof = (~is_ground) & (nz >= roof_upward_threshold)
    is_wall = (~is_ground) & (np.abs(nz) <= wall_vertical_threshold)
    is_other = ~(is_ground | is_roof | is_wall)
    
    def _cface(thickness, rho, cp, fallback):
        """Compute volumetric heat capacity J/m3K from rho*cp*thickness when provided."""
        if thickness is not None and rho is not None and cp is not None:
            try:
                return float(rho) * float(cp) * float(thickness)
            except Exception:
                pass
        return fallback

    cface_ground_val = _cface(rad_thickness_ground, rad_rho_ground, rad_cp_ground, rad_C_face_ground)
    cface_roof_val = _cface(rad_thickness_roof, rad_rho_roof, rad_cp_roof, rad_C_face_roof)
    cface_wall_val = _cface(rad_thickness_wall, rad_rho_wall, rad_cp_wall, rad_C_face_wall)

    C_face = np.empty(F, dtype=np.float64)
    C_face[is_ground] = cface_ground_val
    C_face[is_roof] = cface_roof_val
    C_face[is_wall] = cface_wall_val
    C_face[is_other] = cface_wall_val # Default for other slanted surfaces

    emissivity_face = np.empty(F, dtype=np.float64)
    emissivity_face[is_ground] = rad_emissivity_ground
    emissivity_face[is_roof] = rad_emissivity_roof
    emissivity_face[is_wall] = rad_emissivity_wall
    emissivity_face[is_other] = rad_emissivity_wall # Default
    
    albedo_face = np.empty(F, dtype=np.float64)
    albedo_face[is_ground] = rad_albedo_ground
    albedo_face[is_roof] = rad_albedo_roof
    albedo_face[is_wall] = rad_albedo_wall
    albedo_face[is_other] = rad_albedo_wall # Default
    
    thickness_face = np.empty(F, dtype=np.float64)
    thickness_face[is_ground] = rad_thickness_ground
    thickness_face[is_roof] = rad_thickness_roof
    thickness_face[is_wall] = rad_thickness_wall
    thickness_face[is_other] = rad_thickness_wall # Default

    H = np.full(F, rad_H_default, dtype=np.float64)
    
    # --- Initialize for Cooling Load Calculation ---
    print("[Setup] Initializing variables for cooling load calculation.")
    face_areas = mesh_all.area_faces
    is_facade_or_roof = is_wall | is_roof

    # Calculate CTF coefficients once, assuming uniform properties for all facades/roofs
    if be_concrete_k > 0 and be_concrete_l > 0:
        tau = be_concrete_rho * be_concrete_cp * be_concrete_l**2 / (np.pi**2 * be_concrete_k)
        dt_seconds_ctf = 3600
        decay = np.exp(-dt_seconds_ctf / tau)
        U_val = be_concrete_k / be_concrete_l
        CTF_Y0 = U_val * (1 - decay)
        CTF_Y1 = U_val * decay
        CTF_Phi = decay
    else:
        CTF_Y0, CTF_Y1, CTF_Phi = 0, 0, 0
    
    # Initialize state variables for the CTF model
    q_in_prev = np.zeros(F, dtype=np.float64)
    T_out_prev = np.full(F, be_t_room, dtype=np.float64) # Initialize with default room temp
    cumulative_cooling_load_kWh = np.zeros(F, dtype=np.float64)
    hourly_Q_cooling_W = np.zeros(F, dtype=np.float64)
    # --- End of Cooling Load Initialization ---

    setup_end = time.perf_counter()
    print(f"[PHASE 1 COMPLETE] Total Setup Time: {setup_end - setup_start:.3f} s\n")

    loop_start = time.perf_counter()
    print("[PHASE 2] Starting time-step simulation loop...")
    # Suppress convergence warnings from pythermalcomfort's fsolve, which can occur with certain input value combinations.
    warnings.filterwarnings("ignore", category=RuntimeWarning, message="The iteration is not making good progress.*")
    sim_times = weather_data.index
    dt_seconds = 3600.0

    is_first_iteration = True # Flag to track the first iteration

    for t_sgt in sim_times:
        print(f"\n--- Simulating timestep: {t_sgt} ---")
        weather_now = weather_data.loc[t_sgt]
        time_label = t_sgt.strftime('%Y-%m-%d %H:%M')

        # Extract weather data, using overrides if provided
        wind_dir = wind_dir_override if wind_dir_override is not None else float(weather_now['Wind direction'])
        u10 = wind_speed_override if wind_speed_override is not None else float(weather_now['Wind Speed'])
        T2m = air_temp_override if air_temp_override is not None else float(weather_now['Air Temperature'])
        RH2m = rh_override if rh_override is not None else float(weather_now['Relative Humidity'])
        dni = dni_override if dni_override is not None else float(weather_now.get('Direct Normal Radiation', 0))
        dhi = dhi_override if dhi_override is not None else float(weather_now.get('Diffuse Horizontal Radiation', 0))
        total_radiation = dni + dhi
        
        surface_air_temp_C = T2m # Default to ambient air temp, will be updated by CFD if run

        if run_cfd:
            rot_angle = -wind_dir
            R = trimesh.transformations.rotation_matrix(math.radians(rot_angle), [0, 0, 1])
            rotated_buildings_mesh = cfd_combined_mesh.copy(); rotated_buildings_mesh.apply_transform(R)
            rotated_mesh_for_bounds = mesh_all.copy(); rotated_mesh_for_bounds.apply_transform(R)
            bounds = rotated_mesh_for_bounds.bounds
            x_range = bounds[1, 0] - bounds[0, 0]; y_range = bounds[1, 1] - bounds[0, 1]
            bx = x_range * cfd_buffer_ratio; by = y_range * cfd_buffer_ratio
            x_min, y_min = bounds[0, 0] - bx, bounds[0, 1] - by
            x_max, y_max = bounds[1, 0] + bx, bounds[1, 1] + by
            x_line_rot = np.arange(x_min, x_max, cfd_voxel_pitch); y_line_rot = np.arange(y_min, y_max, cfd_voxel_pitch)
            xv_rot, yv_rot = np.meshgrid(x_line_rot, y_line_rot)
            nx, ny = len(x_line_rot), len(y_line_rot)
            x_world, y_world = rotate_points(xv_rot, yv_rot, wind_dir)
            z0_eff = max(cfd_log_z0, 0.01)
            denom = math.log(max(10.0, z0_eff + 1e-3) / z0_eff)
            slice_results_this_step = []
            slice_2m_data = None # To store 2.0m slice data if found and processed

            for z_slice in slice_heights:
                z_eff = max(z_slice, z0_eff + 1e-3)
                U_slice_base = u10 * math.log(z_eff / z0_eff) / denom if denom > 0 else 0
                
                speed_world_slice = None
                temp_C_slice = None
                rh_percent_slice = None
                
                if np.isclose(z_slice, 0.5):
                    if slice_2m_data is not None:
                        # Generate 0.5m slice data based on 2.0m slice data, skipping potential flow calculation
                        print("    Generating 0.5m slice data based on 2.0m slice data (no potential flow for 0.5m).")
                        
                        # Use 0.5 * 2m speed result for 0.5m slice
                        speed_world_slice = slice_2m_data['speed'] * 0.5
                        
                        # Calculate temp and RH for the *half* speed using the tropical_air_model function
                        temp_C_slice, rh_percent_slice = tropical_air_model(
                            speed=speed_world_slice, T=T2m, RH=RH2m, radiation=total_radiation
                        )
                    else:
                        print("    Warning: 2.0m slice data not found before 0.5m slice. Processing 0.5m slice normally (with potential flow). This should not happen with reordered slice_heights.")
                        # Fallback to normal processing if 2m data is not available (should be rare with reordered slices)
                        pts_slice = np.column_stack([xv_rot.ravel(), yv_rot.ravel(), np.full(nx * ny, z_slice)])
                        solid_mask = rotated_buildings_mesh.contains(pts_slice).reshape(ny, nx)
                        fluid_mask = compute_reachable_fluid_mask(solid_mask)
                        phi = solve_potential_flow(fluid_mask, x_line_rot, U_slice_base)
                        u_rot, v_rot = velocity_from_potential(phi, fluid_mask, cfd_voxel_pitch, cfd_voxel_pitch)
                        u_world_slice, v_world_slice = rotate_points(u_rot, v_rot, wind_dir)
                        speed_world_slice = np.sqrt(u_world_slice**2 + v_world_slice**2)
                        speed_world_slice = apply_physical_speed_limits(speed_world_slice, fluid_mask, U_slice_base * 1.5)
                        temp_C_slice, rh_percent_slice = tropical_air_model(speed=speed_world_slice, T=T2m, RH=RH2m, radiation=total_radiation)
                else:
                    # Process all other slices (including 2.0m) normally with potential flow
                    pts_slice = np.column_stack([xv_rot.ravel(), yv_rot.ravel(), np.full(nx * ny, z_slice)])
                    solid_mask = rotated_buildings_mesh.contains(pts_slice).reshape(ny, nx)
                    fluid_mask = compute_reachable_fluid_mask(solid_mask)
                    phi = solve_potential_flow(fluid_mask, x_line_rot, U_slice_base)
                    u_rot, v_rot = velocity_from_potential(phi, fluid_mask, cfd_voxel_pitch, cfd_voxel_pitch)
                    u_world_slice, v_world_slice = rotate_points(u_rot, v_rot, wind_dir)
                    speed_world_slice = np.sqrt(u_world_slice**2 + v_world_slice**2)
                    speed_world_slice = apply_physical_speed_limits(speed_world_slice, fluid_mask, U_slice_base * 1.5)
                    temp_C_slice, rh_percent_slice = tropical_air_model(speed=speed_world_slice, T=T2m, RH=RH2m, radiation=total_radiation)
                
                # Store results for the current slice
                current_slice_result = {"z": z_slice, "speed": speed_world_slice, "temp": temp_C_slice, "rh": rh_percent_slice}
                slice_results_this_step.append(current_slice_result)
                
                if np.isclose(z_slice, 2.0):
                    # Save 2.0m data for later use by 0.5m slice
                    slice_2m_data = current_slice_result

            slice_sample_data = []
            for res in slice_results_this_step:
                fluid_flat = ~np.isnan(res['speed'].ravel())
                x_flat = x_world.ravel()[fluid_flat]; y_flat = y_world.ravel()[fluid_flat]
                if x_flat.shape[0] == 0:
                    slice_sample_data.append({"tree": None})
                    continue
                tree = cKDTree(np.column_stack([x_flat, y_flat]))
                slice_sample_data.append({"z": res["z"], "tree": tree, "speed": res["speed"].ravel()[fluid_flat], "temp": res["temp"].ravel()[fluid_flat], "rh": res["rh"].ravel()[fluid_flat]})
            
            facet_speed, facet_temp, facet_rh = (np.zeros(F), np.zeros(F), np.zeros(F))
            if any(d.get("tree") is not None for d in slice_sample_data):
                facet_speed, facet_temp, facet_rh = compute_facet_fields_from_slices(mesh_all, slice_sample_data, ground_start)
                surface_air_temp_C = facet_temp # IMPORTANT: Update with per-face temperature
                H = 5.7 + 3.8 * facet_speed
                print(f"    CFD Step Complete. Mean facade wind speed: {np.nanmean(facet_speed):.2f} m/s. Updated H for this step.")
            else:
                H = np.full(F, rad_H_default, dtype=np.float64)
                print("    CFD Step Warning: No valid fluid points found. Using default H.")
            
            # Use facet_temp to initialize T_prev on the first iteration
            if is_first_iteration:
                T_prev = facet_temp + 273.15
                
                # --- START: Visualization of physical properties on first step ---
                print("    Displaying physical properties for the first timestep. Close window to continue.")
                vp_phys = Plotter(shape=(2, 2), size=(1200, 1000), title="Initial Physical Properties")
                vp_phys.show(_cmap_mesh(mesh_all, emissivity_face, title="Emissivity (-) ", filename=os.path.join(vtk_dir, "00_emissivity.vtk")), at=0)
                vp_phys.show(_cmap_mesh(mesh_all, albedo_face, title="Albedo (-) ", filename=os.path.join(vtk_dir, "00_albedo.vtk")), at=1)
                vp_phys.show(_cmap_mesh(mesh_all, C_face, title="Heat Capacity (J/m^2 K)", filename=os.path.join(vtk_dir, "00_heat_capacity.vtk")), at=2)
                vp_phys.show(_cmap_mesh(mesh_all, thickness_face, title="Thickness (m)", filename=os.path.join(vtk_dir, "00_thickness.vtk")), at=3)
                #vp_phys.screenshot(os.path.join(screenshot_dir, "00_initial_physical_properties.png"))
                
                _save_screenshot(vp_phys, os.path.join(screenshot_dir, "00_initial_physical_properties.png"))
                
                if vedo_display_mode == 'interactive':
                    vp_phys.interactive().close()
                elif vedo_display_mode == 'non-interactive':
                    vp_phys.show() # Non-blocking show
                    vp_phys.close()
                else: # 'off'
                    vp_phys.close()
                # --- END: Visualization ---

                is_first_iteration = False
        
        H_used_this_step = H.copy()
        
        if run_radiation:
            sky_lw_from_csv = float(weather_now.get('Horizontal Infrared Radiation Intensity', 0))
            sky_lw = sky_lw_override if sky_lw_override is not None else sky_lw_from_csv
            sky_lw += rad_sky_longwave_offset
            LW_sky_down, LW_surf_down, LW_up_emitted, LW_net, T_faces_K = compute_longwave_components_per_face(
                mesh_all=mesh_all, receivers=receivers, face_indices=face_indices, svf=svf,
                hit_tri_matrix=hit_tri_matrix, rays_vf_weights=rays_vf_weights, # Pass ray data
                sky_longwave=sky_lw, emissivity=emissivity_face, T_faces_K=T_prev
            )
            SW_direct, SW_diffuse, SW_total, _, _ = compute_shortwave_components_per_face(mesh_all, svf, dni, dhi, when_local_sgt=t_sgt, lat=rad_lat, lon=rad_lon, alt=rad_alt, receivers=receivers)
            
            # Convective heat flux
            q_conv = -H_used_this_step * (T_prev - (surface_air_temp_C + 273.15))
            
            # Net radiation for visualization (older, simpler model)
            q_net = SW_total + LW_net + q_conv
            
            # Net radiation for energy balance (more physically correct)
            LW_incoming = LW_sky_down + LW_surf_down
            q_net_balance = (1 - albedo_face) * SW_total + emissivity_face * LW_incoming - LW_up_emitted + q_conv
            
            # Update temperature
            T_new = T_prev + (q_net_balance / C_face) * dt_seconds
            T_surf_C_this_step = T_prev - 273.15
            T_prev = T_new

            # --- Calculate Cooling Load for this timestep ---
            # Apply CTF formula across time series
            # CORRECTED: Use temperature difference (T - T_ref) instead of absolute temperature
            q_in_current = (CTF_Y0 * (T_surf_C_this_step - be_t_room) + 
                            CTF_Y1 * (T_out_prev-be_t_room) + 
                            CTF_Phi * q_in_prev)
            
            # Apply only to facades and roofs, zero out others
            q_in_current[~is_facade_or_roof] = 0.0

            # Hourly cooling load in Watts
            hourly_Q_cooling_W = q_in_current * face_areas

            # Per user request: set cooling load to zero if surface temperature is below room temperature
            hourly_Q_cooling_W[T_surf_C_this_step < be_t_room] = 0.0
            
            # Update cumulative load in kWh (assuming dt_hours is 1.0)
            cumulative_cooling_load_kWh += (hourly_Q_cooling_W * dt_hours) / 1000.0

            # Update state for next iteration
            T_out_prev = T_surf_C_this_step.copy()
            q_in_prev = q_in_current.copy()

            # --- Debug Print for Cooling Load (first 5 facades/roofs) ---
            if 'facade_indices_for_debug' not in locals():
                # Get the first 5 indices that are either a wall or a roof
                facade_indices_for_debug = np.where(is_facade_or_roof)[0][:5]
            
            # Print every 2 hours to avoid excessive log spam
            if t_sgt.hour % 2 == 0:
                print("\n--- Debugging first 5 facade/roof cooling loads ---")
                for i, elem_idx in enumerate(facade_indices_for_debug):
                    print(f"Elem {i} (idx: {elem_idx}): T_surf={T_surf_C_this_step[elem_idx]:.2f}C, Q_cool={hourly_Q_cooling_W[elem_idx]:.2f}W")
                print("-------------------------------------------------")
            # --- End Debug Print ---
            # --- End Cooling Load Calculation ---

            # Calculate MRT at 2m above ground (simplified user model)
            mrt_numerator = 0.5 * (rad_eps_p * LW_incoming + rad_alpha_k * (1 + albedo_face*(1 - albedo_face))*SW_total + rad_eps_p * LW_up_emitted)
            mrt_denominator = rad_eps_p * SIGMA
            
            # Avoid division by zero or invalid values before the root
            mrt_denominator = np.where(mrt_denominator > 1e-9, mrt_denominator, 1e-9)
            safe_ratio = np.clip(mrt_numerator / mrt_denominator, 0, np.inf)
            
            MRT_K = safe_ratio ** 0.25
            MRT_C = MRT_K - 273.15

            # Apply user-specified conditions
            if 'svf' in locals() or 'svf' in globals():
                MRT_C[svf == 0] = 0
            MRT_C = np.clip(MRT_C, 0, None) # Set any MRT < 0 to 0
            
            # Build a mask of all locations where MRT is exactly 0,
            # and turn those values into NaN so they are treated as "no data".
            mrt_zero_mask = (MRT_C == 0.0)
            MRT_C[mrt_zero_mask] = np.nan
            
            # Calculate PET at 2m above ground
            pet_values = None
            slice_data_2m = next((d for d in slice_sample_data if np.isclose(d.get('z', -1), 2.0)), None)

            if slice_data_2m and slice_data_2m.get("tree"):
                ground_centers = mesh_all.triangles_center[is_ground]
                if ground_centers.shape[0] > 0:
                    dist, idx = slice_data_2m["tree"].query(ground_centers[:, :2])
                    
                    tdb_2m = slice_data_2m["temp"][idx]
                    v_2m = slice_data_2m["speed"][idx]
                    rh_2m = slice_data_2m["rh"][idx]
                    tr_2m = MRT_C[is_ground]

                    pet_values = compute_pet_series(
                        tdb_2m, tr_2m, v_2m, rh_2m,
                        met=pet_met, clo=pet_clo, age=pet_age, sex=pet_sex,
                        height=pet_height, weight=pet_weight, p_atm=pet_p_atm,
                        n_debug=5
                    )
                    # Enforce NaN in PET wherever the corresponding ground MRT is NaN (or was 0 before)
                    if 'mrt_zero_mask' in locals():
                        # mrt_zero_mask has the same length as MRT_C (all facets)
                        # Restrict it to ground facets only to match pet_values length
                        ground_zero_mask = mrt_zero_mask[is_ground]
                        # Convert pet_values to a NumPy array if needed
                        pet_values = np.asarray(pet_values, dtype=float)
                        pet_values[ground_zero_mask] = np.nan
            
            if pet_values is None:
                print("    PET calculation skipped: 2m slice data not available.")

        # --- Aggregate per-building metrics and hotspots for analysis summary ---
        try:
            if run_radiation and "analysis_summary" in locals():
                for meta in building_metadata:
                    idx = meta["indices"]
                    if idx.size == 0:
                        continue
                    name = meta["name"]
                    building_entry = analysis_summary["building_metrics"][name]

                    # Surface temperature extremes
                    temps = T_surf_C_this_step[idx]
                    if np.any(np.isfinite(temps)):
                        temp_value = float(np.nanmax(temps))
                        if temp_value > building_entry["max_surface_temp_c"]:
                            face_idx = idx[np.nanargmax(temps)]
                            building_entry["max_surface_temp_c"] = temp_value
                            building_entry["max_surface_temp_time"] = time_label
                            building_entry["max_surface_temp_location"] = tri_centers_all[face_idx].tolist()

                    # Surface wind extremes
                    if "facet_speed" in locals():
                        speeds = facet_speed[idx]
                        if np.any(np.isfinite(speeds)):
                            speed_value = float(np.nanmax(speeds))
                            if speed_value > building_entry["max_surface_wind_ms"]:
                                building_entry["max_surface_wind_ms"] = speed_value
                                building_entry["max_surface_wind_time"] = time_label

                    # Cooling load accumulation
                    if "hourly_Q_cooling_W" in locals():
                        hourly_kw = float(np.nansum(hourly_Q_cooling_W[idx]) / 1000.0)
                        energy_kwh = hourly_kw * dt_hours
                        analysis_summary["cooling_energy"]["per_building_kWh"][name] += energy_kwh
                        analysis_summary["cooling_energy"]["total_kWh"] += energy_kwh
                        peak_entry = analysis_summary["cooling_energy"]["per_building_max_hourly_kw"][name]
                        if hourly_kw > peak_entry["value"]:
                            peak_entry["value"] = hourly_kw
                            peak_entry["time"] = time_label

            if run_radiation and pet_values is not None and ground_start is not None and ground_end is not None:
                ground_face_indices = np.where(is_ground)[0]
                if ground_face_indices.size > 0 and np.any(np.isfinite(pet_values)):
                    local_idx = int(np.nanargmax(pet_values))
                    pet_value = float(pet_values[local_idx])
                    ground_face_idx = ground_face_indices[min(local_idx, ground_face_indices.size - 1)]
                    hotspot_coord = tri_centers_all[ground_face_idx].tolist()
                    neighbors = _nearest_buildings(hotspot_coord[:2], building_metadata, top_k=2)
                    analysis_summary["ground_hotspots"].append(
                        {
                            "time": time_label,
                            "pet_c": pet_value,
                            "location": hotspot_coord,
                            "nearest_buildings": neighbors,
                            "meteorology": {
                                "wind_speed_ms": float(u10),
                                "wind_direction_deg": float(wind_dir),
                                "temperature_c": float(T2m),
                                "relative_humidity_pct": float(RH2m),
                                "dni": float(dni),
                                "dhi": float(dhi),
                            },
                        }
                    )
        except Exception as metrics_error:
            print(f"[Metrics] Warning while aggregating building stats: {metrics_error}")

        # Display visualization only every 3 hours
        if t_sgt.hour % 3 == 0:
            print(f"    Displaying results for {time_label}. Close windows to continue.")

            offscreen_mode = (vedo_display_mode == 'off')
            all_plotters = []

            if run_radiation:
                time_str = t_sgt.strftime('%Y%m%d_%H%M')
                vp_rad = Plotter(shape=(1, 4), size=(2000, 500), title=f"Radiation Fields at {time_label}")
                vp_rad.show(_cmap_mesh(mesh_all, SW_total, title="Total SW (W/m^2 )", filename=os.path.join(vtk_dir, f"rad_SW_total_{time_str}.vtk")), at=0)
                vp_rad.show(_cmap_mesh(mesh_all, LW_net, title="Net LW (W/m^2 )", filename=os.path.join(vtk_dir, f"rad_LW_net_{time_str}.vtk")), at=1)
                vp_rad.show(_cmap_mesh(mesh_all, T_surf_C_this_step, title="Surface Temp (°C)", filename=os.path.join(vtk_dir, f"rad_T_surf_{time_str}.vtk")), at=2)
                vp_rad.show(_cmap_mesh(mesh_all, H_used_this_step, title="Convection H (W/m^2 K)", filename=os.path.join(vtk_dir, f"rad_H_conv_{time_str}.vtk")), at=3)
                
                #vp_rad.screenshot(os.path.join(screenshot_dir, f"rad_fields_{time_str}.png"))
                _save_screenshot(locals().get('vp_rad'),os.path.join(screenshot_dir, f"rad_fields_{time_str}.png"))
                
                all_plotters.append(vp_rad)
            
            if run_cfd:
                vp_slices = Plotter(shape=(len(slice_heights), 3), size=(1400, 900), title=f"CFD Slice Fields at {time_label}")
                base_mesh_cfd = Mesh([cfd_combined_mesh.vertices, cfd_combined_mesh.faces]).c("silver").alpha(1)
                
                slice_results_this_step.sort(key=lambda item: item['z'])

                for row_idx, res in enumerate(slice_results_this_step):
                    fluid_flat = ~np.isnan(res['speed'].ravel())
                    if not np.any(fluid_flat): continue
                    valid_pts = np.column_stack([x_world.ravel()[fluid_flat], y_world.ravel()[fluid_flat], np.full(fluid_flat.sum(), res['z'])])
                    height_text = f"Z = {res['z']:.1f} m"
                    time_str = t_sgt.strftime('%Y%m%d_%H%M')
                    z_str = f"{res['z']:.1f}m".replace('.', 'p')

                    # Create and save Speed points
                    speed_pts = Points(valid_pts, r=cfd_voxel_pitch / 2.2).cmap("plasma", res['speed'].ravel()[fluid_flat])
                    write(speed_pts, os.path.join(vtk_dir, f"cfd_slice_speed_{time_str}_{z_str}.vtk"))
                    speed_title = Text2D(height_text, pos='top-center', s=0.9, c='black')
                    vp_slices.show(base_mesh_cfd.clone(), speed_pts.add_scalarbar("Speed (m/s)"), speed_title, at=row_idx * 3 + 0)

                    # Create and save Temp points
                    temp_pts = Points(valid_pts, r=cfd_voxel_pitch / 2.2).cmap("coolwarm", res['temp'].ravel()[fluid_flat])
                    write(temp_pts, os.path.join(vtk_dir, f"cfd_slice_temp_{time_str}_{z_str}.vtk"))
                    temp_title = Text2D(height_text, pos='top-center', s=0.9, c='black')
                    vp_slices.show(base_mesh_cfd.clone(), temp_pts.add_scalarbar("Temp (°C)"), temp_title, at=row_idx * 3 + 1)

                    # Create and save RH points
                    rh_pts = Points(valid_pts, r=cfd_voxel_pitch / 2.2).cmap("viridis", res['rh'].ravel()[fluid_flat])
                    write(rh_pts, os.path.join(vtk_dir, f"cfd_slice_rh_{time_str}_{z_str}.vtk"))
                    rh_title = Text2D(height_text, pos='top-center', s=0.9, c='black')
                    vp_slices.show(base_mesh_cfd.clone(), rh_pts.add_scalarbar("RH (%)"), rh_title, at=row_idx * 3 + 2)
                
                #vp_slices.screenshot(os.path.join(screenshot_dir, f"cfd_slices_{time_str}.png"))
                _save_screenshot(locals().get('vp_slices'),os.path.join(screenshot_dir, f"cfd_slices_{time_str}.png"))
                
                all_plotters.append(vp_slices)
                
                time_str = t_sgt.strftime('%Y%m%d_%H%M')
                vp_facets = Plotter(shape=(2, 3), size=(1800, 1000), title=f"CFD Surface Fields at {time_label}")
                vp_facets.show(_cmap_mesh(mesh_all, facet_speed, title="Surface Wind Speed (m/s)", filename=os.path.join(vtk_dir, f"facet_wind_speed_{time_str}.vtk")), at=0)
                vp_facets.show(_cmap_mesh(mesh_all, facet_temp, title="Surface Air Temp (°C)", filename=os.path.join(vtk_dir, f"facet_air_temp_{time_str}.vtk")), at=1)
                vp_facets.show(_cmap_mesh(mesh_all, facet_rh, title="Surface RH (%)", filename=os.path.join(vtk_dir, f"facet_rh_{time_str}.vtk")), at=2)
                                                
                ground_face_indices = np.where(is_ground)[0]
                
                # ------------------------------------------------------------------
                # MRT & PET as per-face scalars on the triangle mesh (ground only),
                # with buildings and NaN ground regions drawn as opaque dark gray.
                # ------------------------------------------------------------------
                ground_face_indices = np.where(is_ground)[0]

                if ground_face_indices.size > 0 and 'MRT_C' in locals():
                    # Building mesh (dark gray)
                    building_faces = mesh_all.faces[~is_ground]
                    building_trimesh = trimesh.Trimesh(
                        vertices=mesh_all.vertices,
                        faces=building_faces,
                        process=False,
                    )
                    building_trimesh.remove_unreferenced_vertices()
                    building_mesh_viz = Mesh(
                        [building_trimesh.vertices, building_trimesh.faces]
                    ).c("darkgray").alpha(1.0)

                    # Prepare all ground faces and MRT values
                    ground_faces_all = mesh_all.faces[ground_face_indices]
                    ground_mrt_all = MRT_C[ground_face_indices].astype(float)

                    # SVF Filter: Set MRT to NaN where SVF is 0.
                    if 'svf' in locals() or 'svf' in globals():
                        svf_ground = svf[ground_face_indices]
                        ground_mrt_all[svf_ground == 0.0] = np.nan

                    # Also treat non-positive MRT as invalid.
                    ground_mrt_all[ground_mrt_all <= 0.0] = np.nan

                    # Create a mask for valid vs. invalid values.
                    mrt_valid_mask = np.isfinite(ground_mrt_all)

                    # Create a single mesh for all ground faces with invalid data (NaN).
                    nan_ground_actor = None
                    if np.any(~mrt_valid_mask):
                        nan_faces = ground_faces_all[~mrt_valid_mask]
                        nan_trimesh = trimesh.Trimesh(
                            vertices=mesh_all.vertices,
                            faces=nan_faces,
                            process=False,
                        )
                        nan_trimesh.remove_unreferenced_vertices()
                        nan_ground_actor = Mesh(
                            [nan_trimesh.vertices, nan_trimesh.faces]
                        ).c("darkgray").alpha(1.0)

                    # Color the valid ground faces by MRT value.
                    if np.any(mrt_valid_mask):
                        valid_faces = ground_faces_all[mrt_valid_mask]
                        valid_mrt = ground_mrt_all[mrt_valid_mask]

                        ground_trimesh_valid = trimesh.Trimesh(
                            vertices=mesh_all.vertices,
                            faces=valid_faces,
                            process=False,
                        )
                        ground_trimesh_valid.remove_unreferenced_vertices()

                        mrt_ground_mesh_actor = _cmap_mesh(
                            ground_trimesh_valid,
                            valid_mrt,
                            title="MRT at 2m (°C)",
                            cmap_name="plasma",
                            filename=os.path.join(
                                vtk_dir, f"mrt_on_mesh_{time_str}.vtk"
                            ),
                        )

                        mrt_actors = [building_mesh_viz]
                        if nan_ground_actor is not None:
                            mrt_actors.append(nan_ground_actor)
                        mrt_actors.append(mrt_ground_mesh_actor)

                        vp_facets.show(
                            *mrt_actors,
                            at=3,
                            title="Mean Radiant Temperature (2m)",
                        )
                    else:
                        # If no valid MRT, only draw buildings and NaN ground.
                        mrt_actors = [building_mesh_viz]
                        if nan_ground_actor is not None:
                            mrt_actors.append(nan_ground_actor)
                        vp_facets.show(
                            *mrt_actors,
                            at=3,
                            title="Mean Radiant Temperature (2m)",
                        )

                    # PET on ground mesh
                    if pet_values is not None:
                        pet_vals_all = np.asarray(pet_values, dtype=float).copy()
                        # If MRT is invalid (NaN), the corresponding PET is also NaN.
                        pet_vals_all[~mrt_valid_mask] = np.nan

                        pet_valid_mask = np.isfinite(pet_vals_all)

                        pet_nan_actor = None
                        if np.any(~pet_valid_mask):
                            pet_nan_faces = ground_faces_all[~pet_valid_mask]
                            pet_nan_trimesh = trimesh.Trimesh(
                                vertices=mesh_all.vertices,
                                faces=pet_nan_faces,
                                process=False,
                            )
                            pet_nan_trimesh.remove_unreferenced_vertices()
                            pet_nan_actor = Mesh(
                                [pet_nan_trimesh.vertices, pet_nan_trimesh.faces]
                            ).c("darkgray").alpha(1.0)

                        if np.any(pet_valid_mask):
                            pet_valid_faces = ground_faces_all[pet_valid_mask]
                            pet_valid_vals = pet_vals_all[pet_valid_mask]

                            pet_trimesh_valid = trimesh.Trimesh(
                                vertices=mesh_all.vertices,
                                faces=pet_valid_faces,
                                process=False,
                            )
                            pet_trimesh_valid.remove_unreferenced_vertices()

                            pet_ground_mesh_actor = _cmap_mesh(
                                pet_trimesh_valid,
                                pet_valid_vals,
                                title="PET at 2m (°C)",
                                cmap_name="jet",
                                vmin=25.0,
                                vmax=45.0,
                                filename=os.path.join(
                                    vtk_dir, f"pet_on_mesh_{time_str}.vtk"
                                ),
                            )

                            pet_actors = [building_mesh_viz.clone()]
                            if pet_nan_actor is not None:
                                pet_actors.append(pet_nan_actor)
                            pet_actors.append(pet_ground_mesh_actor)

                            vp_facets.show(
                                *pet_actors,
                                at=4,
                                title="Physiological Equivalent Temp. (2m)",
                            )
                        else:
                            # If all PET are NaN, only draw buildings and NaN ground.
                            pet_actors = [building_mesh_viz.clone()]
                            if pet_nan_actor is not None:
                                pet_actors.append(pet_nan_actor)
                            vp_facets.show(
                                *pet_actors,
                                at=4,
                                title="Physiological Equivalent Temp. (2m)",
                            )
                    else:
                        vp_facets.show(
                            building_mesh_viz,
                            at=4,
                            title="PET (Not Calculated)",
                        )

                else:
                    # If no ground faces or no MRT_C, draw an empty panel.
                    vp_facets.show(at=3, title="Mean Radiant Temperature (2m)")
                    if pet_values is not None:
                        vp_facets.show(
                            at=4,
                            title="Physiological Equivalent Temp. (2m)",
                        )
                    else:
                        vp_facets.show(at=4, title="PET (Not Calculated)")

                
                # Add Hourly Cooling Load plot to the facets window
                if run_radiation:
                    # Use a copy to avoid modifying the original data
                    cooling_load_viz = hourly_Q_cooling_W.copy() / face_areas / 1000.0 # Convert to kW
                    
                    # Define a fixed, stable range for visualization to avoid all-NaN issues.
                    # We calculate an equivalent max load for a 200 W/m^2 scenario for a sensible scale.
                    if 'max_load_for_viz' not in locals():
                        mean_area = np.nanmean(face_areas[is_facade_or_roof]) if np.any(is_facade_or_roof) else 10.0
                        max_load_for_viz = np.max(cooling_load_viz)#200 * mean_area / 1000.0 # Scale max_load for kW
                    
                    vmin, vmax = 0, max_load_for_viz # Ensure vmax is at least 0.1 kW
                    
                    vp_facets.show(_cmap_mesh(mesh_all, cooling_load_viz, title="Energy Use Intensity (kW/m2)", cmap_name='jet', vmin=vmin, vmax=vmax, filename=os.path.join(vtk_dir, f"cooling_load_hourly_{time_str}.vtk")), at=5, title="Hourly Cooling Load (kW)")
                else:
                    vp_facets.show(at=5, title="Cooling Load (Not Calculated)")            # --- Window Management ---
                
                _save_screenshot(locals().get('vp_facets'), os.path.join(screenshot_dir, f"surface_fields_{time_str}.png"))
                all_plotters.append(vp_facets)
                
            #all_plotters = [p for p in (locals().get('vp_rad'), locals().get('vp_slices'), locals().get('vp_facets')) if p is not None]
            
            #if 'vp_facets' in locals() and locals().get('vp_facets') in all_plotters:
            #        locals().get('vp_facets').screenshot(os.path.join(screenshot_dir, f"surface_fields_{time_str}.png"))
            if all_plotters:
                # 1. Always save screenshots and VTK files (VTK is saved during actor creation)
                time_str = t_sgt.strftime('%Y%m%d_%H%M')
                #if 'vp_rad' in locals() and locals().get('vp_rad') in all_plotters:
                #    locals().get('vp_rad').screenshot(os.path.join(screenshot_dir, f"rad_fields_{time_str}.png"))
                #if 'vp_slices' in locals() and locals().get('vp_slices') in all_plotters:
                #    locals().get('vp_slices').screenshot(os.path.join(screenshot_dir, f"cfd_slices_{time_str}.png"))
                #if 'vp_facets' in locals() and locals().get('vp_facets') in all_plotters:
                #    locals().get('vp_facets').screenshot(os.path.join(screenshot_dir, f"surface_fields_{time_str}.png"))
                                
                # 2. Handle display based on mode
                if vedo_display_mode == 'interactive':
                    print("    Displaying plots in interactive mode. Close the final window to continue.")
                    # In interactive mode, show all plots and wait on the last one
                    interactive_plotter = all_plotters[-1]
                    #for p in all_plotters:
                    #    if p is not interactive_plotter:
                    #        p.show() # Show non-blockingly first
                    #interactive_plotter.interactive().close() # Then block on the last one
                    for p in all_plotters[:-1]:
                        p.show()
                    all_plotters[-1].interactive().close()

                elif vedo_display_mode == 'non-interactive':
                    print("    Displaying plots in non-interactive mode.")
                    for p in all_plotters:
                        p.show() # Show all but don't wait

                else: # 'off' mode
                    print("    Vedo display is off. Saving files only.")
                
                # 3. Close all plotter windows to free memory
                for p in all_plotters:
                    p.close()
    loop_end = time.perf_counter()
    try:
        if "analysis_summary" in locals():
            for entry in analysis_summary["building_metrics"].values():
                if not math.isfinite(entry["max_surface_temp_c"]):
                    entry["max_surface_temp_c"] = None
                if not math.isfinite(entry["max_surface_wind_ms"]):
                    entry["max_surface_wind_ms"] = None
            analysis_summary["ground_hotspots"].sort(key=lambda item: item["pet_c"], reverse=True)
            analysis_summary["ground_hotspots"] = analysis_summary["ground_hotspots"][:5]
            with open(analysis_summary_path, "w", encoding="utf-8") as f:
                json.dump(analysis_summary, f, indent=2)
            print(f"[Metrics] Saved analysis summary to {analysis_summary_path}")
    except Exception as summary_error:
        print(f"[Metrics] Failed to persist analysis summary: {summary_error}")

    print(f"\n[PHASE 2 COMPLETE] Main loop finished. Total loop time: {loop_end - loop_start:.3f} s")

    # --- Display Final Cumulative Cooling Load (offscreen-safe) ---
    if run_radiation:
        print("\n[PHASE 2.5] Generating final cumulative visualization.")
        plotter_kwargs = dict(shape=(1, 1), size=(800, 700), title="Cumulative Energy Analysis")
        if vedo_display_mode == 'off':
            plotter_kwargs["offscreen"] = True
        vp_cumulative_energy = Plotter(**plotter_kwargs)
        
        # Filter out near-zero values for better color scale
        cumulative_load_viz = cumulative_cooling_load_kWh.copy()
        cumulative_load_viz[np.abs(cumulative_load_viz) < 0.01] = np.nan # Use nan for colormapping
        
        vp_cumulative_energy.show(
            _cmap_mesh(mesh_all, cumulative_load_viz, title="Cumulative Facade/Roof Cooling Load (kWh)", cmap_name='magma', filename=os.path.join(vtk_dir, "final_cumulative_cooling_load.vtk")),
            at=0,
        )
        _save_screenshot(vp_cumulative_energy, os.path.join(screenshot_dir, "final_cumulative_cooling_load.png"))
        
        if vedo_display_mode == 'interactive':
            vp_cumulative_energy.interactive().close()
        else:
            vp_cumulative_energy.close()
    # --- End of Cumulative Plot ---

    post_proc_start = time.perf_counter()
    print("\n[PHASE 3] Post-processing and exporting final results.")
    post_proc_end = time.perf_counter()
    print(f"[PHASE 3 COMPLETE] Post-processing time: {post_proc_end - post_proc_start:.3f} s")
    total_end_time = time.perf_counter()
    print("\n" + "#"*80)
    print("COUPLED SIMULATION COMPLETE")
    print(f"Total elapsed time: {total_end_time - total_start_time:.3f} s")
    print("#"*80 + "\n")

if __name__ == "__main__":
    # --- USER INPUT SECTION ---
    # Mandatory:
    sim_month_input = 4
    sim_day_input = 15
    
    # Optional (set to a number to override, or None to use weather file data):
    wind_dir_input = None       # e.g., 270 (degrees)
    wind_speed_input = None     # e.g., 5.0 (m/s)
    air_temp_input = None       # e.g., 32.0 (°C)
    rh_input = None             # e.g., 75.0 (%)
    dni_input = None            # e.g., 800.0 (W/m^2)
    dhi_input = None            # e.g., 150.0 (W/m^2)
    sky_lw_input = None         # e.g., 400.0 (W/m^2)

    # Location Parameters (for radiation model calculations)
    latitude_input = 1.3521     # Default to Singapore's latitude
    longitude_input = 103.8198  # Default to Singapore's longitude

    # Visualization settings
    vedo_display_mode_input = 'off' # 'interactive', 'non-interactive', or 'off'
    # --- END OF USER INPUT ---

    main_coupled_run(
        #common_stl_dir=os.path.abspath(r"C:\Users\ccccc\OneDrive - A STAR\Research\AISG\AISG_Joint_Publication\IAQVEC_2026\agentic_ai_251127\town_00001_500_1.379_103.893_14553_1532"),
        common_stl_dir=os.path.abspath(r"C:\Users\ccccc\OneDrive - A STAR\Research\AISG\AISG_Joint_Publication\IAQVEC_2026\agentic_ai_251127\lentor_condo"),
        weather_csv_path="SGP_Singapore_486980_IWEC.csv",
        sim_year=1989,
        sim_month=sim_month_input,
        sim_day=sim_day_input,
        # Pass override values to the main function
        wind_dir_override=wind_dir_input,
        wind_speed_override=wind_speed_input,
        air_temp_override=air_temp_input,
        rh_override=rh_input,
        dni_override=dni_input,
        dhi_override=dhi_input,
        sky_lw_override=sky_lw_input,
        # Location Parameters
        rad_lat=latitude_input,
        rad_lon=longitude_input,
        # Execution flags
        run_radiation=True,
        run_cfd=True,
        vedo_display_mode=vedo_display_mode_input,
    )
