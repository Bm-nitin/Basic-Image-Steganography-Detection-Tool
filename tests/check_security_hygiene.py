import os

patterns = ['c:\\', 'd:\\', 'asus', 'api_key', 'password']
exclusions = ['check_security_hygiene.py', '.png', '.jpg', '.jpeg']

found = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.pytest_cache')]
    for file in files:
        if file in exclusions or any(file.endswith(ext) for ext in ('.png', '.jpg', '.jpeg')):
            continue
        path = os.path.join(root, file)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for idx, line in enumerate(f, 1):
                    lower = line.lower()
                    for pat in patterns:
                        if pat in lower:
                            found.append((path, idx, pat, line.strip()))
        except Exception:
            pass

if found:
    print(f"Warning: Found {len(found)} matches:")
    for p, idx, pat, line in found:
        print(f"  {p}:{idx} [{pat}] -> {line}")
else:
    print("Clean: Zero absolute paths, secrets, credentials, or user directory leaks detected!")
