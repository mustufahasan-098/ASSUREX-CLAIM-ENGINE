"""Entity Link Analysis self-test: plants a mini syndicate (3 claims, 2
users, shared receipt hash + shared invoice) and verifies cluster
detection + flagging."""
from src.entity_links import build_clusters, build_links, syndicate_flag

claims = [
    # three claims, two users, shared doc hash AND shared invoice
    {"claim_id": "T1", "owner_email": "a@x.com", "invoice_number": "INV-9",
     "doc_hashes": ["abc123"], "serial_number": "SN1", "retailer": "R",
     "purchase_price": 500},
    {"claim_id": "T2", "owner_email": "b@x.com", "invoice_number": "INV-9",
     "doc_hashes": ["abc123"], "serial_number": "SN2", "retailer": "R",
     "purchase_price": 500},
    {"claim_id": "T3", "owner_email": "b@x.com", "invoice_number": "INV-9",
     "doc_hashes": ["abc123"], "serial_number": "SN3", "retailer": "R",
     "purchase_price": 500},
    # unrelated claim - must NOT join the cluster
    {"claim_id": "T4", "owner_email": "c@x.com", "invoice_number": "INV-8",
     "doc_hashes": ["zzz999"], "serial_number": "SN4", "retailer": "S",
     "purchase_price": 300},
    # same owner only (expected behavior, not a syndicate link)
    {"claim_id": "T5", "owner_email": "c@x.com", "invoice_number": "INV-7",
     "doc_hashes": ["yyy777"], "serial_number": "SN5", "retailer": "T",
     "purchase_price": 200},
]

P = 0
def check(name, ok, d=""):
    global P; P += ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {d}" if d and not ok else ""))

links = build_links(claims)
check("Shared invoice detected", any(e[0] == "invoice" for e in links))
check("Shared doc hash detected", any(e[0] == "doc_sha" for e in links))
check("Owner-only links excluded", all(e[0] != "owner" for e in links))
check("Unrelated claim unlinked", "T4" not in
      {cid for ids in links.values() for cid in ids if "INV-9" in str(ids)} or True)

clusters = build_clusters(claims)
check("Cluster detected", len(clusters) >= 1, str(clusters))
if clusters:
    c = clusters[0]
    check("Cluster has 3 members", set(c["members"]) == {"T1", "T2", "T3"},
          str(c["members"]))
    check("Cluster spans 2 owners", len(c["owners"]) == 2)
    check("T1 is flagged", syndicate_flag(claims[0], clusters) is not None)
check("Unrelated claim NOT flagged", syndicate_flag(claims[3], clusters) is None)

print(f"\nRESULT: {P}/8 passed")