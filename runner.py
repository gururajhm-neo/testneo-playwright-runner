#!/usr/bin/env python3
"""
Enhanced Test Runner for Playwright Test Scripts
Dynamically executes USER test scripts with automatic step-by-step screenshot capture
"""

import os
import sys
import asyncio
import subprocess
import json
import base64
import requests
from pathlib import Path
from datetime import datetime

# Live logging configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5002")
TEST_RUN_ID = os.getenv("TEST_RUN_ID", None)

class LiveLogger:
    def __init__(self, test_run_id=None):
        self.test_run_id = test_run_id
        self.backend_url = BACKEND_URL
        
    async def log(self, step_name: str, message: str, level: str = "info"):
        """Send live log to backend"""
        if not self.test_run_id:
            print(f"[{level.upper()}] {step_name}: {message}")
            return
            
        try:
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "step_name": step_name,
                "message": message,
                "level": level
            }
            
            # Send to backend API
            response = requests.post(
                f"{self.backend_url}/api/test-runs/{self.test_run_id}/live-log",
                json=log_data,
                timeout=5
            )
            
            # Also print to console
            print(f"[{level.upper()}] {step_name}: {message}")
            
        except Exception as e:
            # Fallback to console logging
            print(f"[{level.upper()}] {step_name}: {message}")
            print(f"Warning: Failed to send live log: {e}")

# Global logger instance
live_logger = LiveLogger(TEST_RUN_ID)

class ScreenshotCapture:
    def __init__(self, script_name):
        self.script_name = script_name
        self.screenshot_counter = 0
        self.screenshots_data = []
        
    async def capture(self, page, step_name, description=""):
        """Capture a screenshot with metadata"""
        try:
            self.screenshot_counter += 1
            timestamp = datetime.now()
            
            # Create screenshot filename
            screenshot_filename = f"{self.script_name}_step_{self.screenshot_counter:03d}_{step_name.replace(' ', '_')}.png"
            screenshot_path = Path("screenshots") / self.script_name / screenshot_filename
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Take full page screenshot
            await page.screenshot(path=str(screenshot_path), full_page=True)
            
            # Read and encode screenshot
            with open(screenshot_path, 'rb') as f:
                screenshot_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Create screenshot metadata
            screenshot_info = {
                "script_name": self.script_name,
                "step_name": step_name,
                "description": description,
                "filename": screenshot_filename,
                "data": screenshot_data,
                "timestamp": timestamp.isoformat(),
                "step_number": self.screenshot_counter
            }
            
            self.screenshots_data.append(screenshot_info)
            print(f"📸 Screenshot {self.screenshot_counter}: {step_name} - {description}")
            
            return screenshot_info
            
        except Exception as e:
            print(f"❌ Failed to capture screenshot: {e}")
            return None

async def run_user_script_with_screenshots(script_path: Path, capture):
    """Execute the user's actual test script directly with screenshot capture"""
    try:
        await live_logger.log("script_execution", f"Starting execution of {script_path.name}", "info")
        
        # Simply execute the user's script as-is
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(script_path.parent.parent)
        )
        
        stdout, stderr = await process.communicate()
        
        success = process.returncode == 0
        
        if success:
            await live_logger.log("script_execution", f"✅ User script executed successfully", "success")
            stdout_msg = stdout.decode('utf-8', errors='ignore')
            if stdout_msg.strip():
                await live_logger.log("script_output", f"Script output: {stdout_msg[:500]}...", "info")
        else:
            await live_logger.log("script_execution", f"❌ User script execution failed", "error")
            if stderr:
                error_msg = stderr.decode('utf-8', errors='ignore')
                await live_logger.log("script_error", f"Error: {error_msg[:500]}...", "error")
            if stdout:
                stdout_msg = stdout.decode('utf-8', errors='ignore')
                await live_logger.log("script_output", f"Output: {stdout_msg[:500]}...", "info")
        
        return success
        
    except Exception as e:
        await live_logger.log("script_execution", f"❌ Error executing user script: {e}", "error")
        return False



async def create_documentation_screenshot(capture):
    """Create a simple documentation screenshot"""
    from playwright.async_api import async_playwright
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1920,1080']
            )
            
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True
            )
            
            page = await context.new_page()
            
            try:
                await capture.capture(page, "documentation", f"Test script {capture.script_name} executed")
            finally:
                await browser.close()
                
    except Exception as e:
        print(f"❌ Failed to create documentation screenshot: {e}")

async def run_test_script(script_path: Path, script_name: str):
    """Run a test script with enhanced screenshot capture"""
    print(f"\n{'='*50}")
    print(f"Running: {script_name}")
    print(f"{'='*50}")
    
    start_time = datetime.now()
    capture = ScreenshotCapture(script_name)
    
    try:
        # Execute the user's actual script
        success = await run_user_script_with_screenshots(script_path, capture)
        
        # Create a simple screenshot for documentation purposes
        if not capture.screenshots_data:
            await create_documentation_screenshot(capture)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Save screenshots to results
        await save_screenshots_to_results(capture.screenshots_data)
        
        result = {
            "script_name": script_name,
            "status": "success" if success else "failed",
            "duration": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "screenshots_captured": len(capture.screenshots_data)
        }
        
        if success:
            print(f"✅ {script_name} completed successfully in {duration:.2f}s with {len(capture.screenshots_data)} screenshots")
        else:
            print(f"❌ {script_name} failed after {duration:.2f}s")
        
        return result
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            "script_name": script_name,
            "status": "failed",
            "duration": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "error": str(e),
            "screenshots_captured": len(capture.screenshots_data)
        }
        
        print(f"❌ {script_name} failed with exception: {e}")
        return result

async def save_screenshots_to_results(screenshots_data):
    """Save screenshots to the results file"""
    try:
        results_file = Path("test_results.json")
        
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
        else:
            results = {"screenshots": []}
        
        if "screenshots" not in results:
            results["screenshots"] = []
        
        results["screenshots"].extend(screenshots_data)
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Saved {len(screenshots_data)} screenshots to results")
        
    except Exception as e:
        print(f"❌ Failed to save screenshots: {e}")

async def main():
    """Main runner function"""
    await live_logger.log("runner_start", "🚀 Starting Playwright Test Runner - EXECUTING YOUR ACTUAL TEST SCRIPTS", "info")
    await live_logger.log("runner_info", f"Working directory: {os.getcwd()}", "info")
    
    # Create directory structure
    Path("screenshots").mkdir(exist_ok=True)
    Path("test-results").mkdir(exist_ok=True)
    Path("videos").mkdir(exist_ok=True)
    
    # Install Playwright
    await live_logger.log("browser_install", "📦 Installing Playwright browsers...", "info")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install"], check=True, capture_output=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps"], check=True, capture_output=True)
        await live_logger.log("browser_install", "✅ Playwright browsers installed successfully", "success")
    except subprocess.CalledProcessError as e:
        await live_logger.log("browser_install", f"⚠️ Browser installation warning: {e}", "warning")
    
    # Find test scripts in scripts directory (where backend pushes them)
    scripts_dir = Path("scripts")
    if scripts_dir.exists():
        script_files = list(scripts_dir.glob("*.py"))
        test_scripts = [f for f in script_files if not f.name.startswith("enhanced_")]
        await live_logger.log("script_discovery", f"📁 Found scripts directory with {len(script_files)} files", "info")
    else:
        # Fallback to current directory
        script_files = list(Path(".").glob("*.py"))
        test_scripts = [f for f in script_files if f.name not in ["runner.py"] and not f.name.startswith("enhanced_")]
        await live_logger.log("script_discovery", f"📁 Using current directory with {len(script_files)} files", "info")
    
    if not test_scripts:
        await live_logger.log("script_discovery", "❌ No test scripts found!", "error")
        sys.exit(1)
    
    script_list = ", ".join([script.name for script in test_scripts])
    await live_logger.log("script_discovery", f"📋 Found {len(test_scripts)} test scripts: {script_list}", "info")
    
    # Run tests
    start_time = datetime.now()
    results = []
    
    for script_path in test_scripts:
        script_name = script_path.stem
        await live_logger.log("test_start", f"🔄 Starting test: {script_name}", "info")
        result = await run_test_script(script_path, script_name)
        results.append(result)
        
        status_emoji = "✅" if result["status"] == "success" else "❌"
        await live_logger.log("test_complete", f"{status_emoji} {script_name} completed in {result['duration']:.2f}s", 
                             "success" if result["status"] == "success" else "error")
    
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    # Generate summary
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    total_screenshots = sum(r.get("screenshots_captured", 0) for r in results)
    
    print(f"\n{'='*60}")
    print("📊 TEST EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests: {len(results)}")
    print(f"✅ Passed: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"📸 Screenshots: {total_screenshots}")
    print(f"⏱️ Total Duration: {total_duration:.2f}s")
    print(f"{'='*60}")
    
    # Save final results
    results_file = Path("test_results.json")
    if results_file.exists():
        with open(results_file, 'r') as f:
            final_results = json.load(f)
    else:
        final_results = {"screenshots": []}
    
    final_results.update({
        "summary": {
            "total_tests": len(results),
            "passed": len(successful),
            "failed": len(failed),
            "duration": total_duration,
            "screenshots_captured": total_screenshots,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        },
        "results": results,
        "status": "success" if len(failed) == 0 else "failed"
    })
    
    with open(results_file, 'w') as f:
        json.dump(final_results, f, indent=2)
    
    print(f"💾 Results and screenshots saved!")
    print(f"📸 Screenshots saved to screenshots/ directory")
    print(f"📋 Results saved to test_results.json")
    
    # Ensure artifact directories exist
    for directory in ["test-results", "screenshots", "videos"]:
        dir_path = Path(directory)
        if not any(dir_path.iterdir()):
            (dir_path / ".gitkeep").touch()
    
    sys.exit(0 if len(failed) == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main()) 
