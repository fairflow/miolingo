#!/usr/bin/env python3
"""
Diagnostic script to test IPA generation from espeak-ng
"""
import subprocess
import sys

def get_espeak_path():
    """Find espeak executable"""
    from pathlib import Path
    
    # Try macOS MacPorts path first
    local_path = "/opt/local/bin/espeak"
    if Path(local_path).exists():
        return local_path
    
    # Try espeak-ng (Streamlit Cloud / Ubuntu)
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return "espeak-ng"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fallback to espeak (if available in PATH)
    return "espeak"

def test_ipa_generation(text: str, lang_code: str):
    """Test IPA generation for a phrase"""
    ESPEAK_LANG_MAP = {
        'pt': 'pt-br',
        'fr': 'fr-fr',
        'nl': 'nl',
        'de': 'de',
        'it': 'it',
        'es': 'es'
    }
    
    espeak_lang = ESPEAK_LANG_MAP.get(lang_code, lang_code)
    espeak_cmd = get_espeak_path()
    
    print(f"\n{'='*60}")
    print(f"Testing: '{text}' (lang: {lang_code})")
    print(f"Espeak command: {espeak_cmd}")
    print(f"Espeak voice: {espeak_lang}")
    print(f"{'='*60}")
    
    try:
        # Test 1: Check if espeak-ng is available
        version_result = subprocess.run(
            [espeak_cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"\n✓ Espeak version check:")
        print(f"  {version_result.stdout.strip()}")
        
        # Test 2: Generate IPA
        cmd = [espeak_cmd, '-v', espeak_lang, '-q', '--ipa', text]
        print(f"\n✓ Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        print(f"\n✓ Return code: {result.returncode}")
        print(f"✓ Stdout length: {len(result.stdout)} chars")
        print(f"✓ Stderr length: {len(result.stderr)} chars")
        
        if result.returncode == 0:
            ipa = result.stdout.strip()
            ipa_cleaned = ' '.join(ipa.split())
            
            print(f"\n✓ Raw IPA output:")
            print(f"  '{result.stdout}'")
            print(f"\n✓ Stripped IPA:")
            print(f"  '{ipa}'")
            print(f"\n✓ Cleaned IPA:")
            print(f"  '{ipa_cleaned}'")
            print(f"\n✓ IPA is empty: {ipa == ''}")
            print(f"✓ IPA is whitespace only: {ipa.isspace() if ipa else 'N/A'}")
            
            if ipa:
                print(f"\n✓ SUCCESS: Generated IPA")
                print(f"  Final result: [{ipa_cleaned}]")
                return ipa_cleaned
            else:
                print(f"\n✗ PROBLEM: IPA is empty!")
                return None
        else:
            print(f"\n✗ PROBLEM: Non-zero return code")
            if result.stderr:
                print(f"  Stderr: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"\n✗ PROBLEM: Command timeout")
        return None
    except Exception as e:
        print(f"\n✗ PROBLEM: Exception: {e}")
        import traceback
        traceback.print_exc()
        return None

# Test cases
test_cases = [
    ("Bom dia", "pt"),
    ("Bonjour", "fr"),
    ("Goedemorgen", "nl"),
    ("Guten Morgen", "de"),
]

print("\n" + "="*60)
print("ESPEAK-NG IPA GENERATION DIAGNOSTIC TEST")
print("="*60)

results = {}
for text, lang in test_cases:
    ipa = test_ipa_generation(text, lang)
    results[(text, lang)] = ipa

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
for (text, lang), ipa in results.items():
    status = "✓ SUCCESS" if ipa else "✗ FAILED"
    print(f"{status}: '{text}' ({lang}) → {f'[{ipa}]' if ipa else 'NO IPA'}")
