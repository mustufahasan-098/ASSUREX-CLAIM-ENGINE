"""addlinks.py - wires Entity Link Analysis into the app.
Patches app.py (route + nav), claim_service.py (syndicate check),
fusion.py (escalation rule), settings.yaml (config). Safe pattern:
anchors, backup, syntax check, rollback. Idempotent."""
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
CS = ROOT / "src" / "claim_service.py"
FU = ROOT / "src" / "fusion.py"
CFG = ROOT / "config" / "settings.yaml"
NL = chr(10)
changed_files = []


def patch(path, anchor, insert, label, insert_before=False):
    content = path.read_text(encoding="utf-8")
    if label.split(":")[0] in content and anchor not in content:
        print(f"  [SKIP] {label}")
        return
    n = content.count(anchor)
    if n != 1:
        print(f"  [FAIL] {label}: anchor x{n} - MANUAL needed")
        return
    if insert_before:
        pos = content.find(anchor)
        content = content[:pos] + insert + NL + content[pos:]
    else:
        pos = content.find(anchor) + len(anchor)
        content = content[:pos] + NL + insert + content[pos:]
    backup = path.with_suffix(path.suffix + ".bak")
    if path not in changed_files:
        shutil.copy(path, backup)
        changed_files.append(path)
    path.write_text(content, encoding="utf-8")
    print(f"  [OK]   {label}")


def main():
    print("=" * 60)
    print("ENTITY LINKS INSTALLER")
    print("=" * 60)

    # ---- 1. app.py: route + nav
    print("\n[1] app.py")
    patch(APP,
          'if __name__ == "__main__":',
          ('# ------------------------------------------------ entity links' + NL +
           '@app.route("/admin/links")' + NL +
           '@login_required(roles=["admin", "reviewer"])' + NL +
           'def entity_links():' + NL +
           '    from src import entity_links as el' + NL +
           '    claims = fdb.all_docs("claims", limit=1000)' + NL +
           '    links = el.build_links(claims)' + NL +
           '    try:' + NL +
           '        min_c = int(models_mod.load_all()["settings"]' + NL +
           '                    .get("syndicate_min_cluster", 3))' + NL +
           '    except Exception:' + NL +
           '        min_c = 3' + NL +
           '    clusters = el.build_clusters(claims, min_cluster=min_c,' + NL +
           '                                  min_link_types=2)' + NL +
           '    cluster_ids = {cid for cl in clusters' + NL +
           '                   for cid in cl["members"]}' + NL +
           '    return render_template("entity_links.html",' + NL +
           '                           total_claims=len(claims), links=links,' + NL +
           '                           clusters=clusters,' + NL +
           '                           cluster_claims=len(cluster_ids))' + NL + NL +
           ''),
          "ENTITY-LINKS-ROUTE: /admin/links route",
          insert_before=True)

    patch(APP,
          '("admin_templates", "Product Catalog",',
          '              ("entity_links", "Entity Links", "\U0001F517"),',
          "ENTITY-LINKS-NAV: sidebar entry",
          insert_before=True)

    # ---- 2. claim_service.py: syndicate check after fraud analyze
    print("\n[2] src/claim_service.py")
    patch(CS,
          'fraud = fraud_intel.analyze(',
          ('    # syndicate cluster check: membership in a multi-user' + NL +
           '    # shared-entity cluster escalates regardless of predictions' + NL +
           '    from src import entity_links as el' + NL +
           '    try:' + NL +
           '        _all = fdb.all_docs("claims", limit=1000)' + NL +
           '        _cluster = el.syndicate_flag(' + NL +
           '            claim, el.build_clusters(_all))' + NL +
           '    except Exception:' + NL +
           '        _cluster = None' + NL +
           '    if _cluster:' + NL +
           '        dup["fraud_score"] = max(' + NL +
           '            int(dup.get("fraud_score", 0) or 0), 85)' + NL +
           '        dup["syndicate_cluster"] = _cluster["members"]' + NL +
           '        claim["_dup"] = dup' + NL +
           ''),
          "SYNDICATE-CHECK: fraud_score max 85 cluster")

    # ---- 3. fusion.py: escalation rule
    print("\n[3] src/fusion.py")
    patch(FU,
          'fs = int(dup.get("fraud_score", 0) or 0)',
          ('    if dup.get("syndicate_cluster"):' + NL +
           '        oppose.append(f"Potential fraud ring: claim is part of a linked "' + NL +
           '                      f"cluster ({\', \'.join(dup[\'syndicate_cluster\'][:4])}) "' + NL +
           '                      f"sharing entities across users - escalated to "' + NL +
           '                      f"priority review")' + NL +
           '        if final in ("Likely Valid", "Likely Invalid"):' + NL +
           '            final = "Manual Review Required"'),
          "SYNDICATE-ESCALATE: fusion rule")

    # ---- 4. settings.yaml
    print("\n[4] config/settings.yaml")
    cfg = CFG.read_text(encoding="utf-8")
    if "syndicate_min_cluster" in cfg:
        print("  [SKIP] config already present")
    else:
        CFG.write_text(cfg.rstrip() + NL + "syndicate_min_cluster: 3" + NL,
                       encoding="utf-8")
        print("  [OK]   syndicate_min_cluster: 3")

    # ---- syntax checks
    print("\n[5] Syntax checks")
    for p, name in [(APP, "app.py"), (CS, "claim_service.py"),
                    (FU, "fusion.py")]:
        if p in changed_files:
            try:
                py_compile.compile(str(p), doraise=True)
                print(f"  [OK]   {name} syntax OK")
            except py_compile.PyCompileError as e:
                bak = p.with_suffix(p.suffix + ".bak")
                shutil.copy(bak, p)
                sys.exit(f"[ABORT] {name} failed - backup restored.\n{e}")

    print("\n" + "=" * 60)
    print("DONE. Next:")
    print("  1. python test_entity_links.py   -> expect 8/8")
    print("  2. Restart Flask, admin sidebar -> Entity Links")
    print("  3. Commit. FREEZE.")


if __name__ == "__main__":
    main()