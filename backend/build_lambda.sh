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
mkdir package
# Now that we removed textstat/regex, everything is pure Python!
# We can just install simply.
pip install -r requirements.txt --target ./package --upgrade

# 5. Create the zip file
echo "Zipping dependencies..."
cd package
zip -r9 ../lambda.zip . > /dev/null
cd ..

# 6. Add the lambda function code
echo "Adding function code..."
zip -g lambda.zip lambda_function.py

# 7. Clean up
deactivate
rm -rf package
rm -rf temp_venv

# 8. Verification
echo "----------------------------------------------------------------"
echo "Verifying 'feedparser' is in the zip..."
unzip -l lambda.zip | grep feedparser | head -n 5
echo "----------------------------------------------------------------"
echo "Done! 'lambda.zip' is ready."
echo "Please upload this specific file to AWS Console."
