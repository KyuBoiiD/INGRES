import sys
import subprocess

print(f"🐍 Python Path: {sys.executable}")
print("🔧 Forcing upgrade of Google AI library...")

try:
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", 
        "--upgrade", "--force-reinstall", "google-generativeai"
    ])
    print("\n✅ SUCCESS! Library updated.")
    
    # Verify version
    import google.generativeai as genai
    print(f"📚 New Version: {genai.__version__}")
    
    if int(genai.__version__.split('.')[1]) >= 7:
        print("🎉 YOU ARE READY! Run 'python app.py' now.")
    else:
        print("⚠️ Version is still too low. Something is blocking the update.")
        
except Exception as e:
    print(f"❌ Error: {e}")