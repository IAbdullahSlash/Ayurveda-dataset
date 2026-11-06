"""Exclude held-out record concepts and exact/near-duplicate descriptions."""
import re
import unicodedata
from collections import defaultdict

def normalized(text):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',str(text)).casefold()))

def concept_exclusions(seed_ids, members):
    banned=set(seed_ids)
    groups=[set(group.entity_id.astype(str)) for _,group in members.groupby('concept_id')]
    changed=True
    while changed:
        before=len(banned)
        for group in groups:
            if group & banned:
                banned.update(group)
        changed=len(banned)!=before
    return banned

class DescriptionGuard:
    def __init__(self, descriptions):
        self.exact={normalized(text) for text in descriptions}
        # Training passages are truncated to 400 characters downstream.
        self.exact.update(normalized(str(text)[:400]) for text in descriptions)
        self.tokens=[set(text.split()) for text in self.exact if len(text.split())>=5]
        self.index=defaultdict(set)
        for i,tokens in enumerate(self.tokens):
            for token in tokens:
                self.index[token].add(i)
    def overlaps(self, text):
        value=normalized(text)
        if value in self.exact or normalized(str(text)[:400]) in self.exact:
            return True
        tokens=set(value.split())
        if len(tokens)<5:
            return False
        candidates=set().union(*(self.index.get(t,set()) for t in tokens))
        for i in candidates:
            other=self.tokens[i]
            if len(tokens & other)/len(tokens | other)>=0.9:
                return True
        return False
