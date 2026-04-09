"""
Visualization utilities for Solar and CFD results.
Includes enhanced interpolation and multi-panel plotting.
"""
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import griddata


class VisualizationUtils:
    """Shared visualization utilities."""

    @staticmethod
    def interpolate_grid(
        df: pd.DataFrame,
        value_col: str,
        res_m: float = 2.0,
        method: str = "linear"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Interpolate scattered data onto a regular grid.
        
        Args:
            df: DataFrame with 'x', 'y', and value_col columns
            value_col: Name of the column to interpolate
            res_m: Grid resolution in meters
            method: Interpolation method ('linear', 'nearest', 'cubic')
            
        Returns:
            Tuple of (X_grid, Y_grid, Z_grid)
        """
        x = df["x"].values
        y = df["y"].values
        z = df[value_col].values

        # Define grid
        x_min, x_max = x.min(), x.max()
        y_min, y_max = y.min(), y.max()
        
        # Add slight buffer
        buffer = res_m * 2
        xi = np.arange(x_min - buffer, x_max + buffer, res_m)
        yi = np.arange(y_min - buffer, y_max + buffer, res_m)
        xi, yi = np.meshgrid(xi, yi)

        # Interpolate
        zi = griddata((x, y), z, (xi, yi), method=method)
        
        return xi, yi, zi

    @staticmethod
    def plot_solar_analysis(
        df_surface: pd.DataFrame,
        output_dir: Path,
        timestamp_str: str,
        resolution: float = 2.0
    ) -> Dict[str, str]:
        """
        Generate enhanced solar visualizations.
        
        Returns:
            Dictionary mapping plot type to file path
        """
        plots = {}
        
        try:
            # 1. Interpolated Heatmap
            xi, yi, zi = VisualizationUtils.interpolate_grid(
                df_surface, "sw", res_m=resolution
            )
            
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(
                zi,
                extent=[xi.min(), xi.max(), yi.min(), yi.max()],
                origin="lower",
                cmap="inferno",
                aspect="equal",
                vmin=0,
                vmax=max(1000, np.nanmax(zi))
            )
            
            # Overlay original points faintly to show sampling density
            ax.scatter(
                df_surface["x"], 
                df_surface["y"], 
                c="white", 
                s=1, 
                alpha=0.1
            )
            
            ax.set_title(f"Solar Irradiance Distribution\n{timestamp_str}")
            ax.set_xlabel("x (m)")
            ax.set_ylabel("y (m)")
            plt.colorbar(im, ax=ax, label="Shortwave Irradiance (W/m²)")
            
            heatmap_path = output_dir / "solar_irradiance_map.png"
            fig.savefig(heatmap_path, dpi=300, bbox_inches="tight")
            plt.close(fig)
            plots["heatmap"] = str(heatmap_path)
            
            # 2. Histogram distribution
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.hist(df_surface["sw"].dropna(), bins=50, color="orange", edgecolor="black", alpha=0.7)
            ax.set_title(f"Irradiance Distribution\n{timestamp_str}")
            ax.set_xlabel("Irradiance (W/m²)")
            ax.set_ylabel("Count")
            ax.grid(True, alpha=0.3)
            
            hist_path = output_dir / "solar_distribution_hist.png"
            fig.savefig(hist_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            plots["histogram"] = str(hist_path)
            
        except Exception as e:
            print(f"Error generating solar plots: {e}")
            
        return plots

    @staticmethod
    def plot_cfd_analysis(
        df_field: pd.DataFrame,
        output_dir: Path,
        wind_dir_deg: float,
        resolution: float = 2.0
    ) -> Dict[str, str]:
        """
        Generate enhanced CFD visualizations.
        """
        plots = {}
        
        try:
            # Interpolate velocity
            xi, yi, vel_grid = VisualizationUtils.interpolate_grid(
                df_field, "velocity", res_m=resolution
            )
            # Interpolate temperature
            _, _, temp_grid = VisualizationUtils.interpolate_grid(
                df_field, "air_temp", res_m=resolution
            )
            
            # 1. Velocity Streamlines/Quiver
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Background speed map
            im = ax.imshow(
                vel_grid,
                extent=[xi.min(), xi.max(), yi.min(), yi.max()],
                origin="lower",
                cmap="viridis",
                aspect="equal",
                alpha=0.8
            )
            
            # Add streamlines if we can infer u/v components or assume uniform flow direction locally
            # Since we only have magnitude in df_field for some solvers, we might skip streamlines 
            # unless we reconstruct them. Assuming potential flow direction matches wind_dir mostly:
            # For better viz, let's just show the magnitude map with high quality first.
            
            ax.set_title(f"Wind Speed Distribution (Inflow: {wind_dir_deg}°)")
            ax.set_xlabel("x (m)")
            ax.set_ylabel("y (m)")
            plt.colorbar(im, ax=ax, label="Wind Speed (m/s)")
            
            vel_path = output_dir / "cfd_velocity_map.png"
            fig.savefig(vel_path, dpi=300, bbox_inches="tight")
            plt.close(fig)
            plots["velocity"] = str(vel_path)
            
            # 2. Combined Environmental Map
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
            
            # Temperature
            im1 = ax1.imshow(
                temp_grid,
                extent=[xi.min(), xi.max(), yi.min(), yi.max()],
                origin="lower",
                cmap="coolwarm",
                aspect="equal"
            )
            ax1.set_title("Air Temperature (°C)")
            plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
            
            # Humidity (if available)
            if "humidity" in df_field.columns:
                _, _, hum_grid = VisualizationUtils.interpolate_grid(
                    df_field, "humidity", res_m=resolution
                )
                im2 = ax2.imshow(
                    hum_grid,
                    extent=[xi.min(), xi.max(), yi.min(), yi.max()],
                    origin="lower",
                    cmap="Blues",
                    aspect="equal"
                )
                ax2.set_title("Relative Humidity (%)")
                plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
            
            plt.tight_layout()
            env_path = output_dir / "cfd_environmental_maps.png"
            fig.savefig(env_path, dpi=300, bbox_inches="tight")
            plt.close(fig)
            plots["environmental"] = str(env_path)
            
        except Exception as e:
            print(f"Error generating CFD plots: {e}")
            
        return plots

