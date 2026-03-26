import os
import subprocess
import time
import sys
import shutil

# Check if colorama is available, if not, use a dummy
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class Dummy:
        def __getattr__(self, name): return ""
    Fore = Style = Dummy()

BANNER = rf"""
{Fore.CYAN}{Style.BRIGHT}
   _____                      _      _____                      _      
  / ____|                    | |    / ____|                    | |     
 | (___  _ __ ___   __ _ _ __| |_  | (___   ___  __ _ _ __ ___| |__    
  \___ \| '_ ` _ \ / _` | '__| __|  \___ \ / _ \/ _` | '__/ __| '_ \   
  ____) | | | | | | (_| | |  | |_   ____) |  __/ (_| | | | (__| | | |  
 |_____/|_| |_| |_|\__,_|_|   \__| |_____/ \___|\__,_|_|  \___|_| |_|  
                                                                       
                     🧪 TEST RUNNER - PRESTIGE EDITION 🧪
{Style.RESET_ALL}
"""

def get_pytest_path():
    paths = [
        os.path.join("venv", "Scripts", "pytest.exe"),
        os.path.join("venv", "bin", "pytest"),
        "pytest"
    ]
    for p in paths:
        if shutil.which(p):
            return p
    return None

def run_test(pytest_path, test_file):
    cmd = [pytest_path, "-v", test_file]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8"
    )
    return process

def main():
    if sys.platform == "win32":
        os.system("title SmartSearch Test Runner")

    print(BANNER)
    
    pytest_path = get_pytest_path()
    if not pytest_path:
        print(f"{Fore.RED}❌ Error: 'pytest' not found.")
        return

    test_dir = "tests"
    test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]
    
    results = []
    terminal_width = 80
    try:
        terminal_width = shutil.get_terminal_size().columns
    except:
        pass

    for i, test_file in enumerate(test_files):
        count_str = f"[{i+1}/{len(test_files)}]"
        print(f"{Fore.BLACK}{Style.BRIGHT}{count_str} {Fore.WHITE}Executing {Fore.CYAN}{test_file}...", flush=True)
        
        start_time = time.time()
        process = run_test(pytest_path, os.path.join(test_dir, test_file))
        stdout, _ = process.communicate()
        duration = time.time() - start_time
        
        if process.returncode == 0:
            print(f"{Fore.BLACK}{Style.BRIGHT}{count_str} {Fore.GREEN}SUCCESS {Fore.WHITE}{test_file} {Fore.BLACK}{Style.BRIGHT}({duration:.2f}s)")
        else:
            print(f"{Fore.BLACK}{Style.BRIGHT}{count_str} {Fore.RED}FAILURE {Fore.WHITE}{test_file} {Fore.BLACK}{Style.BRIGHT}({duration:.2f}s)")

        # Detailed test cases
        for line in stdout.splitlines():
            line = line.strip()
            if "::" in line and ("PASSED" in line or "FAILED" in line or "XPASS" in line or "XFAIL" in line):
                parts = line.split(" ")
                test_path = parts[0]
                test_name = test_path.split("::")[-1]
                
                status_str = "PASSED" if "PASSED" in line else "FAILED"
                status_color = Fore.GREEN if "PASSED" in line else Fore.RED
                
                print(f"    {Fore.BLACK}{Style.BRIGHT}└─ {Fore.WHITE}{test_name:<60} {status_color}{status_str}")
        
        results.append((test_file, "PASS" if process.returncode == 0 else "FAIL", duration, stdout))

    passed_count = sum(1 for _, status, _, _ in results if status == "PASS")
    success_rate = (passed_count / len(results)) * 100
    final_color = Fore.GREEN if success_rate == 100 else (Fore.YELLOW if success_rate > 0 else Fore.RED)
    
    print(f"\n{Style.BRIGHT}OVERALL SUCCESS RATE: {final_color}{success_rate:.1f}%")
    print(f"{Fore.WHITE}Total test suites: {len(results)} | Passed: {Fore.GREEN}{passed_count} {Fore.WHITE}| Failed: {Fore.RED}{len(results)-passed_count}")
    
    if success_rate == 100:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}SUCCESS: All tasks completed successfully.")
    else:
        print(f"\n{Fore.RED}{Style.BRIGHT}FAILURE: {len(results)-passed_count} failure(s) found.")
        for test_file, status, _, logs in results:
            if status == "FAIL":
                print(f"\n{Fore.RED}{Style.BRIGHT}--- Failure Detail: {test_file} ---")
                print(f"{Fore.WHITE}" + "\n".join(logs.strip().splitlines()[-20:]))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}🛑 Interrupted.")
        sys.exit(1)
