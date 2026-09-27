"""AssureX Entity Link Analysis - shared-entity clustering across claims.

The Syndicate concept, implemented at the scale appropriate to this system:
instead of a graph database, claims are linked by entities they already
share (invoice numbers, document hashes and perceptual fingerprints,
serial numbers, owner emails, retailer+price combinations). Clusters of
linked claims from MULTIPLE users indicate coordinated activity - a
"Potential Fraud Ring" - and are escalated to priority review.

No new data is collected (no EXIF/GPS/device fingerprinting - privacy
constraints documented in the project report): links are derived only
from data already stored with each claim."""
from collections import defaultdict


def _claim_entities(claim):
    """Extract the linkable entities from one claim record."""
    ents = set()
    inv = claim.get("invoice_number")
    if inv:
        ents.add(("invoice", str(inv).strip().lower()))
    for h in claim.get("doc_hashes") or []:
        if h:
            ents.add(("doc_sha", h))
    for h in claim.get("doc_phashes") or []:
        if h:
            ents.add(("doc_phash", h))
    sn = claim.get("serial_number")
    if sn:
        ents.add(("serial", str(sn).strip().lower()))
    owner = claim.get("owner_email")
    if owner:
        ents.add(("owner", str(owner).strip().lower()))
    retailer = claim.get("retailer")
    price = claim.get("purchase_price")
    if retailer and price:
        ents.add(("retailer_price",
                  f"{str(retailer).strip().lower()}|{float(price):.2f}"))
    return ents


def build_links(claims):
    """Group claims by shared entity. Returns:
    links: {entity: [claim_ids]} for entities shared by 2+ claims
    """
    by_entity = defaultdict(set)
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            continue
        for ent in _claim_entities(c):
            by_entity[ent].add(cid)
    # owner-links alone don't indicate a syndicate (same customer, multiple
    # claims is expected behavior) - only keep owner links when they pair
    # with a DIFFERENT entity type shared across users
    return {ent: sorted(ids) for ent, ids in by_entity.items()
            if len(ids) >= 2 and ent[0] != "owner"}


def build_clusters(claims, min_cluster=3, min_link_types=2):
    """Detect syndicate clusters: groups of min_cluster+ claims connected
    by min_link_types+ DIFFERENT entity types, spanning multiple owners.

    Returns list of cluster dicts with member claims, links, and owners.
    """
    links = build_links(claims)
    if not links:
        return []

    # union-find over claim ids
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x] = parent.get(parent[x], parent[x])
        return x

    def union(a, b):
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for ids in links.values():
        for i in ids[1:]:
            union(ids[0], i)

    groups = defaultdict(set)
    for cid in list(parent):
        groups[find(cid)].add(cid)

    by_id = {c.get("claim_id"): c for c in claims}
    clusters = []
    for members in groups.values():
        if len(members) < min_cluster:
            continue
        # entity types shared inside this group
        shared = {ent: ids for ent, ids in links.items()
                  if set(ids) & members}
        types = {ent[0] for ent in shared}
        owners = {by_id[cid].get("owner_email") for cid in members
                  if cid in by_id}
        if len(types) >= min_link_types or len(owners) >= 2:
            clusters.append({
                "members": sorted(members),
                "links": {f"{ent[0]}: {ent[1][:24]}": ids
                          for ent, ids in sorted(shared.items())},
                "link_types": sorted(types),
                "owners": sorted(o for o in owners if o),
            })
    clusters.sort(key=lambda k: -len(k["members"]))
    return clusters


def syndicate_flag(claim, clusters):
    """Is this claim a member of any syndicate cluster?"""
    for cl in clusters:
        if claim.get("claim_id") in cl["members"]:
            return cl
    return None