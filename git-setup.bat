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


@REM  Here are the step-by-step methods to do this using either the command line or the GitHub web interface.
@REM  Method 1: Using the Git Command Line
@REM  Open your terminal or command prompt inside your project folder and run the following commands:
@REM  1. Switch to the main branch:bash
@REM  git checkout main
@REM  Use code with caution.
@REM  (Note: If you haven't created your main branch locally yet, run git checkout -b main instead).
@REM  2. Fetch and pull the latest changes to ensure your local repository is up to date:bash
@REM  git pull origin main
@REM  Use code with caution.
@REM  3. Merge master into main:bash
@REM  git merge master
@REM  Use code with caution.
@REM  Note: If Git throws an error saying "fatal: refusing to merge unrelated histories", it means the two branches do not share a common commit history. You can bypass this by adding a flag:bash
@REM  git merge master --allow-unrelated-histories
@REM  Use code with caution.
@REM  4. Resolve conflicts (if any):
@REM  If there are conflicting changes between the two branches, your code editor (like VS Code) will prompt you to choose which changes to keep. Once resolved, stage and commit the changes:bash
@REM  git add .
@REM  git commit -m "Merge master into main"
@REM  Use code with caution.
@REM  5. Push the merged changes to GitHub:bash
@REM  git push origin main
@REM  Use code with caution.
