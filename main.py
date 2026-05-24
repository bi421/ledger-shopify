import sys
import os

# Get the absolute paths for this workspace
current_dir = os.path.dirname(os.path.abspath(__file__))

# Force the project root into sys.path to resolve the 'src.' namespace correctly
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    import uvicorn
    
    print("\n=== STARTING TRUEROAS PRODUCTION ENGINE ===")
    
    # Standardized import using the src.trueroas namespace
    from src.trueroas.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=8000)