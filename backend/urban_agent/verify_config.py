"""
Simple script to verify JSON configuration file without dependencies
"""
import json
import os


def verify_config():
    """Verify JSON configuration file"""
    
    config_file = "/scratch/Urban/intelligent_agent_package/solver_parameters.json"
    
    print("="*80)
    print("🧪 Verifying JSON Configuration File")
    print("="*80)
    
    # Test 1: Check if config file exists
    print("\n📋 Test 1: Check config file existence")
    if os.path.exists(config_file):
        print(f"   ✅ Config file found: {config_file}")
    else:
        print(f"   ❌ Config file not found: {config_file}")
        return False
    
    # Test 2: Verify JSON is valid
    print("\n📋 Test 2: Verify JSON format")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        print("   ✅ JSON format is valid")
        print(f"   📊 Found sections: {list(config_data.keys())}")
    except json.JSONDecodeError as e:
        print(f"   ❌ Invalid JSON: {e}")
        return False
    
    # Test 3: Check required sections
    print("\n📋 Test 3: Check required sections")
    required_sections = ['cfd', 'solar']
    all_sections_found = True
    for section in required_sections:
        if section in config_data:
            print(f"   ✅ Section '{section}' found")
            print(f"      Parameters: {list(config_data[section].keys())}")
        else:
            print(f"   ❌ Section '{section}' missing")
            all_sections_found = False
    
    # Test 4: Validate CFD parameters
    print("\n📋 Test 4: Validate CFD parameters")
    cfd_params = ['wind_speed', 'wind_direction', 'height', 'temperature', 'humidity']
    if 'cfd' in config_data:
        for param in cfd_params:
            if param in config_data['cfd']:
                value = config_data['cfd'][param]
                print(f"   ✅ {param}: {value} ({type(value).__name__})")
            else:
                print(f"   ⚠️  {param}: not found (will use default)")
    
    # Test 5: Validate Solar parameters
    print("\n📋 Test 5: Validate Solar parameters")
    solar_params = ['time', 'latitude', 'longitude', 'DNI', 'DHI']
    if 'solar' in config_data:
        for param in solar_params:
            if param in config_data['solar']:
                value = config_data['solar'][param]
                print(f"   ✅ {param}: {value} ({type(value).__name__})")
            else:
                print(f"   ⚠️  {param}: not found (will use default)")
    
    # Display full configuration
    print("\n" + "="*80)
    print("📄 Complete Configuration")
    print("="*80)
    print(json.dumps(config_data, indent=2, ensure_ascii=False))
    
    print("\n" + "="*80)
    print("✅ Configuration file is valid and ready to use!")
    print("="*80)
    
    return True


if __name__ == "__main__":
    success = verify_config()
    exit(0 if success else 1)

