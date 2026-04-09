# Material Properties for Urban Microclimate Simulation

This document provides a compilation of thermal and radiative properties for common urban materials, intended for use in parametric studies for microclimate simulations. The properties listed are essential for accurately modeling the energy balance at building and ground surfaces.

## 1. Key Material Properties

The following properties are critical for the energy balance calculations in the simulation:

*   **Albedo (α)**: Also known as Solar Reflectance. It is a dimensionless fraction (`0` to `1`) representing the amount of incoming solar radiation reflected by a surface. A low albedo means the surface absorbs more sunlight, while a high albedo means it reflects more.
*   **Emissivity (ε)**: A dimensionless fraction (`0` to `1`) representing the efficiency with which a surface emits thermal energy as longwave radiation. Most non-metallic building materials have a high emissivity.
*   **Thermal Conductivity (k)**: Measures a material's ability to conduct heat. It is expressed in **W/(m·K)**. Low conductivity materials are good insulators.
*   **Density (ρ)**: The mass per unit volume of a material, expressed in **kg/m³**.
*   **Specific Heat Capacity (cₚ)**: The amount of heat energy required to raise the temperature of a unit mass of a substance by one degree, expressed in **J/(kg·K)**. Materials with high specific heat capacity can store more thermal energy.

The product `ρ * cₚ` gives the **Volumetric Heat Capacity (J/m³·K)**, which determines how much energy a given volume of material can store.

---

## 2. Facade Materials

Values are typical and can vary based on color, age, and surface texture.

| Material           | Albedo (α)  | Emissivity (ε) | Thermal Conductivity (k) [W/(m·K)] | Density (ρ) [kg/m³] | Specific Heat (cₚ) [J/(kg·K)] |
| ------------------ | ----------- | -------------- | -------------------------------------- | ------------------- | --------------------------------- |
| **Concrete** (grey) | 0.20 - 0.35 | 0.90 - 0.94    | 1.4 - 1.7                              | 2200 - 2400         | 880 - 920                         |
| **Brick** (red)      | 0.20 - 0.40 | 0.90 - 0.92    | 0.6 - 1.0                              | 1600 - 1900         | 800 - 850                         |
| **Stucco** (white)   | 0.60 - 0.80 | 0.85 - 0.92    | 0.6 - 0.8                              | 1800 - 2000         | 840                               |
| **Glass** (reflective) | 0.5 - 0.8 | 0.84           | 1.05                                   | 2500                | 750 - 840                         |
| **Aluminum Panel**   | 0.6 - 0.8 | 0.2 - 0.4      | 160 - 200                              | 2700                | 900                               |
| **Painted Steel**    | 0.1 - 0.7   | 0.85 - 0.95    | 45 - 55                                | 7850                | 490                               |

*Sources: ASHRAE Handbook of Fundamentals; Oke, T. R. (1988), "Boundary Layer Climates"; LBNL Heat Island Group.*

---

## 3. Roof Materials

Roofing properties, especially albedo, have a significant impact on building energy use and the urban heat island effect.

| Material                 | Albedo (α)  | Emissivity (ε) | Notes on Thermal Properties (k, ρ, cₚ)                                     |
| ------------------------ | ----------- | -------------- | -------------------------------------------------------------------------- |
| **Asphalt Shingles** (dark) | 0.08 - 0.20 | 0.90 - 0.92    | Thermal properties are primarily from the underlying roof deck (e.g., plywood). |
| **Concrete Tiles** (grey)  | 0.20 - 0.40 | 0.90           | k: 1.1, ρ: 2000, cₚ: 840                                                   |
| **Metal Roof** (unpainted) | 0.50 - 0.70 | 0.1 - 0.2      | Low emissivity traps heat. Properties are for the metal itself.              |
| **Cool Roof** (white membrane) | 0.70 - 0.85 | 0.85 - 0.95    | A thin layer; thermal properties depend on insulation and structure below. |
| **Green Roof** (extensive)   | 0.20 - 0.35 | 0.95           | Properties are for the soil/substrate layer. Highly dependent on moisture. |

*Sources: Cool Roof Rating Council (CRRC); U.S. EPA, "Reducing Urban Heat Islands: Compendium of Strategies"; Sailor, D. J. (2008), "A green roof model for building energy simulation programs."*

---

## 4. Ground Surfaces

| Material             | Albedo (α)  | Emissivity (ε) | Thermal Conductivity (k) [W/(m·K)] | Density (ρ) [kg/m³] | Specific Heat (cₚ) [J/(kg·K)] |
| -------------------- | ----------- | -------------- | -------------------------------------- | ------------------- | --------------------------------- |
| **Asphalt Pavement** (new) | 0.05 - 0.10 | 0.93 - 0.95    | 0.75 - 1.5                             | 2100 - 2300         | 920                               |
| **Asphalt Pavement** (aged) | 0.10 - 0.20 | 0.93 - 0.95    | 0.75 - 1.5                             | 2100 - 2300         | 920                               |
| **Concrete Pavement**  | 0.25 - 0.40 | 0.92 - 0.95    | 1.4 - 1.7                              | 2200 - 2400         | 880                               |
| **Grass/Soil** (dry)   | 0.20 - 0.25 | 0.95           | 0.3 - 0.8                              | 1200 - 1600         | 800 - 1200                        |
| **Grass/Soil** (wet)   | 0.10 - 0.20 | 0.98           | 1.2 - 2.5                              | 1800 - 2200         | 1200 - 1800                       |
| **Gravel**             | 0.15 - 0.35 | 0.92           | 0.3 - 0.5                              | 1500 - 1700         | 800                               |

*Sources: Oke, T. R. (1988), "Boundary Layer Climates"; Jo, J. H., & Golden, J. S. (2017), "In-situ measurements of thermal and radiative properties of urban surfaces"; ASHRAE Handbook.*

---

### Notes for Parametric Study

*   When changing materials, ensure you update all relevant parameters (`albedo`, `emissivity`, and the thermal properties for heat transfer calculations).
*   For composite surfaces like roofs and walls, the **surface properties** (albedo, emissivity) are most critical for the radiation model, while the **bulk properties** (k, ρ, cₚ, thickness) are critical for the thermal conduction and storage model (`Building Energy Model`).
*   The values provided are typical. For a detailed study, it is recommended to consult specific manufacturer data or more detailed literature for the exact materials being considered.
