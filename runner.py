#!/usr/bin/env python3
"""
Test Runner for Playwright Test Scripts
Dynamically executes all test scripts from the scripts/ directory
with proper logging, error handling, and screenshot capture.
"""

import os
import sys
import asyncio
import subprocess
import glob
import json
import base64
from pathlib import Path
from datetime import datetime
import tempfile
import shutil


class TestRunner:
    def __init__(self, scripts_dir="scripts"):
        self.scripts_dir = Path(scripts_dir)
        self.results = []
        self.start_time = datetime.now()
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        
    def ensure_headless_mode(self, script_path):
        """Patch headless=False to headless=True in script files and add screenshot capture"""
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace various headless patterns
            original_content = content
            content = content.replace("headless=False", "headless=True")
            content = content.replace("headless = False", "headless = True")
            content = content.replace('"headless": false', '"headless": true')
            content = content.replace("'headless': False", "'headless': True")
            
            # Add screenshot capture functionality
            if "async def" in content and "playwright" in content:
                # Add screenshot capture after page creation
                if "page = await browser.new_page()" in content:
                    screenshot_code = f'''
        # Auto-screenshot capture
        screenshot_dir = Path("screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        script_name = "{script_path.stem}"
        
        async def capture_screenshot(step_name):
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                screenshot_path = screenshot_dir / f"{{script_name}}_{{step_name}}_{{timestamp}}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"📸 Screenshot saved: {{screenshot_path}}")
                return str(screenshot_path)
            except Exception as e:
                print(f"⚠️ Screenshot failed: {{e}}")
                return None
'''
                    # Insert the screenshot function after page creation
                    content = content.replace(
                        "page = await browser.new_page()",
                        f"page = await browser.new_page(){screenshot_code}"
                    )
                    
                    # Add screenshots at key points
                    content = content.replace(
                        'await page.goto(',
                        'await capture_screenshot("page_load")\n        await page.goto('
                    )
                    content = content.replace(
                        'await browser.close()',
                        'await capture_screenshot("final_state")\n        await browser.close()'
                    )
                    
                    # Add datetime import if not present
                    if "from datetime import datetime" not in content:
                        content = "from datetime import datetime\nfrom pathlib import Path\n" + content
            
            # Write back if changed
            if content != original_content:
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Patched headless mode and added screenshots in {script_path.name}")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not patch script {script_path.name}: {e}")
    
    async def ensure_browsers_installed(self):
        """Ensure Playwright browsers are installed"""
        try:
            print("🔍 Checking Playwright browser installation...")
            
            # Try to check if browsers are installed
            result = subprocess.run([
                sys.executable, "-c", 
                "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(); p.stop()"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Playwright browsers are already installed and working")
                return True
            else:
                print("⚠️  Playwright browsers not working, installing...")
                print(f"Error: {result.stderr}")
                
                # Install browsers
                install_result = subprocess.run([
                    "playwright", "install", "--with-deps", "chromium"
                ], capture_output=True, text=True, timeout=300)
                
                if install_result.returncode == 0:
                    print("✅ Successfully installed Playwright browsers")
                    return True
                else:
                    print(f"❌ Failed to install browsers: {install_result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error checking/installing browsers: {e}")
            return False
    
    def collect_screenshots(self, script_name):
        """Collect screenshots generated during test execution"""
        screenshots = []
        try:
            for screenshot_file in self.screenshots_dir.glob(f"{script_name}_*.png"):
                try:
                    # Read and encode screenshot as base64
                    with open(screenshot_file, 'rb') as f:
                        screenshot_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    # Extract step name from filename
                    filename_parts = screenshot_file.stem.split('_')
                    step_name = '_'.join(filename_parts[1:-1]) if len(filename_parts) > 2 else "unknown"
                    
                    screenshots.append({
                        "step_name": step_name,
                        "filename": screenshot_file.name,
                        "data": screenshot_data,
                        "timestamp": screenshot_file.stat().st_mtime
                    })
                except Exception as e:
                    print(f"⚠️ Error processing screenshot {screenshot_file}: {e}")
            
            # Sort by timestamp
            screenshots.sort(key=lambda x: x["timestamp"])
            
        except Exception as e:
            print(f"⚠️ Error collecting screenshots: {e}")
        
        return screenshots
    
    async def run_single_script(self, script_path):
        """Run a single test script and capture output with screenshots"""
        script_name = script_path.stem
        print(f"\n{'='*60}")
        print(f"🚀 RUNNING: {script_name}")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        
        try:
            # Ensure headless mode and add screenshot capture
            self.ensure_headless_mode(script_path)
            
            # Set environment variables for Playwright
            env = os.environ.copy()
            
            # Force proper environment setup
            if "HOME" not in env or not env["HOME"]:
                env["HOME"] = os.path.expanduser("~")
            
            # Set Playwright browser path
            browser_path = os.path.join(env["HOME"], ".cache", "ms-playwright")
            env["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
            
            print(f"🏠 Home directory: {env['HOME']}")
            print(f"🎭 Playwright browsers path: {browser_path}")
            print(f"📁 Working directory: {Path.cwd()}")
            
            # Check if browser path exists
            if os.path.exists(browser_path):
                print(f"✅ Browser path exists: {browser_path}")
                # List contents
                try:
                    contents = os.listdir(browser_path)
                    print(f"📂 Browser path contents: {contents}")
                except Exception as e:
                    print(f"⚠️  Could not list browser path: {e}")
            else:
                print(f"❌ Browser path does not exist: {browser_path}")
            
            # Run the script from repository root
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
                env=env
            )
            
            stdout, stderr = await process.communicate()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Decode output
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""
            
            # Collect screenshots
            screenshots = self.collect_screenshots(script_name)
            
            # Determine success/failure
            success = process.returncode == 0
            status = "✅ PASSED" if success else "❌ FAILED"
            
            result = {
                'script': script_name,
                'status': status,
                'success': success,
                'duration': duration,
                'return_code': process.returncode,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'screenshots': screenshots,
                'start_time': start_time,
                'end_time': end_time
            }
            
            self.results.append(result)
            
            # Print results
            print(f"\n📊 RESULT: {status}")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"🔢 Return Code: {process.returncode}")
            print(f"📸 Screenshots: {len(screenshots)}")
            
            if stdout_text:
                print(f"\n📤 STDOUT:")
                print("-" * 40)
                print(stdout_text)
            
            if stderr_text:
                print(f"\n📥 STDERR:")
                print("-" * 40)
                print(stderr_text)
            
            print(f"{'='*60}")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_result = {
                'script': script_name,
                'status': "❌ ERROR",
                'success': False,
                'duration': duration,
                'return_code': -1,
                'stdout': "",
                'stderr': str(e),
                'screenshots': [],
                'start_time': start_time,
                'end_time': end_time,
                'error': str(e)
            }
            
            self.results.append(error_result)
            
            print(f"\n💥 ERROR: {e}")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"{'='*60}")
            
            return error_result
    
    async def run_all_scripts(self):
        """Run all Python scripts in the scripts directory"""
        print(f"\n🎯 TEST RUNNER STARTED")
        print(f"📁 Scripts Directory: {self.scripts_dir.absolute()}")
        print(f"🕐 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🏠 Working Directory: {Path.cwd()}")
        print(f"📸 Screenshots Directory: {self.screenshots_dir.absolute()}")
        
        # Ensure browsers are installed before running tests
        browsers_ready = await self.ensure_browsers_installed()
        if not browsers_ready:
            print("❌ Cannot proceed without working Playwright browsers")
            return
        
        # Find all Python scripts
        if not self.scripts_dir.exists():
            print(f"❌ Scripts directory '{self.scripts_dir}' does not exist!")
            return
        
        script_files = list(self.scripts_dir.glob("*.py"))
        
        if not script_files:
            print(f"⚠️  No Python scripts found in '{self.scripts_dir}'")
            return
        
        print(f"📜 Found {len(script_files)} test scripts:")
        for script in script_files:
            print(f"   - {script.name}")
        
        # Run all scripts
        tasks = []
        for script_path in script_files:
            task = self.run_single_script(script_path)
            tasks.append(task)
        
        # Wait for all scripts to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Save results with screenshots
        self.save_results()
        
        # Print summary
        self.print_summary()
    
    def save_results(self):
        """Save test results including screenshots to JSON file"""
        try:
            results_file = Path("test_results.json")
            with open(results_file, 'w', encoding='utf-8') as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_results = []
                for result in self.results:
                    serializable_result = result.copy()
                    serializable_result['start_time'] = result['start_time'].isoformat()
                    serializable_result['end_time'] = result['end_time'].isoformat()
                    serializable_results.append(serializable_result)
                
                json.dump({
                    'execution_time': self.start_time.isoformat(),
                    'total_scripts': len(self.results),
                    'passed': sum(1 for r in self.results if r['success']),
                    'failed': sum(1 for r in self.results if not r['success']),
                    'results': serializable_results
                }, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results saved to: {results_file.absolute()}")
            
        except Exception as e:
            print(f"⚠️ Error saving results: {e}")
    
    def print_summary(self):
        """Print execution summary"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        passed = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - passed
        total_screenshots = sum(len(r.get('screenshots', [])) for r in self.results)
        
        print(f"\n{'='*80}")
        print(f"📊 TEST EXECUTION SUMMARY")
        print(f"{'='*80}")
        print(f"🕐 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕑 End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        print(f"📜 Total Scripts: {len(self.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📸 Total Screenshots: {total_screenshots}")
        print(f"📈 Success Rate: {(passed/len(self.results)*100):.1f}%" if self.results else "0%")
        
        print(f"\n📋 DETAILED RESULTS:")
        print("-" * 80)
        
        for result in self.results:
            duration_str = f"{result['duration']:.2f}s"
            screenshot_count = len(result.get('screenshots', []))
            print(f"{result['status']:<12} {result['script']:<30} {duration_str:>8} 📸{screenshot_count}")
        
        print(f"{'='*80}")
        
        # Set exit code based on results
        if failed > 0:
            print(f"🚨 {failed} test(s) failed. Exiting with code 1.")
            sys.exit(1)
        else:
            print(f"🎉 All {passed} test(s) passed successfully!")
            sys.exit(0)


def main():
    """Main entry point"""
    print("🎭 Playwright Test Runner with Screenshots")
    print("=" * 50)
    
    # Check if Playwright is installed
    try:
        import playwright
        print("✅ Playwright is available")
    except ImportError:
        print("❌ Playwright not found. Please install it first:")
        print("   pip install playwright")
        print("   playwright install --with-deps")
        sys.exit(1)
    
    # Initialize and run
    runner = TestRunner()
    
    try:
        asyncio.run(runner.run_all_scripts())
    except KeyboardInterrupt:
        print("\n🛑 Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
