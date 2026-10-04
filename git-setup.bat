@echo off
echo Setting up Git repository...
echo.

REM Initialize git repository
git init

REM Add all files
git add .

REM Create first commit
git commit -m "Initial commit: Smart Business Intelligence Dashboard"

echo.
echo Repository initialized!
echo.
echo Next steps:
echo 1. Go to GitHub and create a new repository
echo 2. Copy the repository URL (e.g., https://github.com/yourusername/serpapi-business-intelligence.git)
echo 3. Run: git remote add origin YOUR_REPOSITORY_URL
echo 4. Run: git push -u origin main
echo.
pause
