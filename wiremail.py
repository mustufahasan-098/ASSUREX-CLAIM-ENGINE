"""wiremail3.py - wires email to all 4 claim events. v3 design:
  - insert blocks built with chr(10) (immune to escaping)
  - anchors are SHORT single lines (no multiline matching)
  - self-verifies with counts at the end
Idempotent, backup, syntax check, rollback."""
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
NL = chr(10)


def block(lines):
    return NL.join(lines) + NL


def main():
    print("=" * 60)
    print("EMAIL WIRING v3 (marker-based)")
    print("=" * 60)
    content = APP.read_text(encoding="utf-8")
    changed = False
    results = []

    # ---- WIRE 1: claim submission (anchor: _clear_staging + redirect)
    print("\n[1] claim submission email")
    marker1 = 'f"AssureX claim {result[' + chr(39) + 'claim_id' + chr(39) + ']} submitted"'
    if marker1 in content:
        print("  [SKIP] already wired")
        results.append(("submission", True))
    else:
        anchor = '_clear_staging()' + NL + '    return redirect(url_for("claim_detail", cid=result["claim_id"]))'
        if anchor in content:
            ins = block([
                '    _clear_staging()',
                '    from src import email_service',
                '    email_service.send_email(',
                '        owner,',
                '        "AssureX claim " + result["claim_id"] + " submitted",',
                '        "Your warranty claim " + result["claim_id"] + " has been submitted and evaluated."',
                '        + "\\nDecision: " + result["decision"]["final"]',
                '        + "\\nLog in to view the full analysis.\\n\\n- AssureX Claim Engine")',
                '    return redirect(url_for("claim_detail", cid=result["claim_id"]))',
            ])
            content = content.replace(anchor, ins, 1)
            changed = True
            print("  [OK]   wired")
            results.append(("submission", True))
        else:
            print("  [FAIL] anchor not found")
            results.append(("submission", False))

    # ---- WIRE 2: approve/reject email
    print("\n[2] approve/reject email")
    anchor2 = 'f"Claim {cid} {status.lower()} by reviewer.")'
    if 'notify_claim_decision(c.get("owner_email"), cid, status)' in content:
        print("  [SKIP] already wired")
        results.append(("decision", True))
    elif content.count(anchor2) == 1:
        ins = block([
            '',
            '    from src import email_service',
            '    email_service.notify_claim_decision(c.get("owner_email"), cid, status)',
        ])
        pos = content.find(anchor2) + len(anchor2)
        content = content[:pos] + NL + ins.rstrip(NL) + content[pos:]
        changed = True
        print("  [OK]   wired")
        results.append(("decision", True))
    else:
        print(f"  [FAIL] anchor count: {content.count(anchor2)}")
        results.append(("decision", False))

    # ---- WIRE 3: request-info email
    print("\n[3] request-info email")
    anchor3 = 'additional information required'
    already3 = ('notify_claim_decision(' in content and
                'Additional information required"' in content)
    if already3:
        print("  [SKIP] already wired")
        results.append(("info-request", True))
    else:
        idx = content.find('f"Claim {cid}: additional information required')
        if idx > 0:
            end = content.find(')', content.find('{comment or', idx))
            if end > 0:
                end += 1
                ins = block([
                    '',
                    '        from src import email_service',
                    '        email_service.notify_claim_decision(',
                    '            c.get("owner_email"), cid, "Additional information required")',
                ])
                content = content[:end] + NL + ins.rstrip(NL) + content[end:]
                changed = True
                print("  [OK]   wired")
                results.append(("info-request", True))
        else:
            print("  [FAIL] anchor not found")
            results.append(("info-request", False))

    # ---- WIRE 4: repair dispatch email
    print("\n[4] repair dispatch email")
    marker4 = '"AssureX claim " + cid + ": repair scheduled"'
    if marker4 in content:
        print("  [SKIP] already wired")
        results.append(("dispatch", True))
    else:
        idx = content.find("repair scheduled at {center['name']}")
        if idx > 0:
            end = content.find(')', content.find("{center['phone']}", idx))
            if end > 0:
                end += 1
                ins = block([
                    '',
                    '    from src import email_service',
                    '    email_service.send_email(',
                    '        c.get("owner_email"),',
                    '        "AssureX claim " + cid + ": repair scheduled",',
                    '        "Your approved claim " + cid + " has been scheduled for repair at "',
                    '        + center["name"] + " (" + center["city"] + ")."',
                    '        + "\\nExpected completion by: " + deadline',
                    '        + "\\nContact: " + center["phone"] + "\\n\\n- AssureX Claim Engine")',
                ])
                content = content[:end] + NL + ins.rstrip(NL) + content[end:]
                changed = True
                print("  [OK]   wired")
                results.append(("dispatch", True))
        else:
            print("  [FAIL] anchor not found")
            results.append(("dispatch", False))

    # ---- save + verify
    if not changed:
        print("\nNothing to change.")
        return
    backup = ROOT / "app.py.bak9"
    shutil.copy(APP, backup)
    APP.write_text(content, encoding="utf-8")
    try:
        py_compile.compile(str(APP), doraise=True)
        print(f"\n  [OK]   syntax check PASSED (backup: app.py.bak9)")
    except py_compile.PyCompileError as e:
        shutil.copy(backup, APP)
        sys.exit(f"[ABORT] syntax failed - backup restored.\n{e}")

    # ---- final count verification
    count = content.count("from src import email_service")
    print(f"\n  [VERIFY] 'from src import email_service' appears {count}x "
          f"(expect 5)")
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"  [NOTE] not wired: {failed} - paste app.py sections for "
              f"manual patch")
    print("\nDONE. Restart Flask + run the 4 email tests.")


if __name__ == "__main__":
    main()