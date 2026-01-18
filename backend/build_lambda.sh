#!/bin/bash
set -e # Stop on error

# 1. Clean up previous build
echo "Cleaning up..."
rm -rf package
rm -f lambda.zip
rm -rf temp_venv

# 2. Create a virtual environment to ensure we have fresh pip
echo "Creating temporary virtual environment..."
python3 -m venv temp_venv
source temp_venv/bin/activate

# 3. Upgrade pip to handle cross-platform wheels better
echo "Upgrading pip..."
pip install --upgrade pip

# 4. Install dependencies
echo "Installing dependencies..."
mkdir -p package

# Pass 1: Install all requirements normally
pip install \
    --target ./package \
    --upgrade \
    -r requirements.txt

# Pass 2: Surgical Binary Patch
# We force-reinstall the compiled libraries specifically for Linux (x86_64)
# using --no-deps to avoid re-triggering resolution conflicts.
echo "Surgically patching binaries for Linux (x86_64) on Python 3.14..."
pip install \
    --platform manylinux2014_x86_64 \
    --target ./package \
    --implementation cp \
    --python-version 3.14 \
    --only-binary=:all: \
    --upgrade \
    --force-reinstall \
    --no-deps \
    pydantic-core pydantic httpx httpcore anyio 

# 5. Create the zip file
echo "Zipping dependencies..."
cd package
# Remove any existing .so files that might be Mac-specific if they weren't overwritten
# (though force-reinstall should handle it)
zip -r9 ../lambda.zip . > /dev/null
cd ..

# 6. Add the lambda function code
echo "Adding function code..."
zip -g lambda.zip lambda_function.py

# 7. Clean up
deactivate
rm -rf temp_venv

# 8. Verification
echo "----------------------------------------------------------------"
echo "Verifying Linux binary (.so) is present..."
unzip -l lambda.zip | grep "_pydantic_core" | head -n 3
echo "----------------------------------------------------------------"
echo "Done! 'lambda.zip' is ready."
echo "Please upload this specific file to AWS Console."
