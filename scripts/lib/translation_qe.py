"""Detect consecutive decoding loops without treating ordinary symptom lists as loops."""
FUNCTION_WORDS={'के','की','का','में','से','को','पर','और','है','हैं','एक','या','तथा','भी'}
def has_decoding_loop(text):
    # Whitespace tokenization preserves Devanagari combining marks.
    tokens=[token.strip('.,;:।!?()') for token in text.split() if token.strip('.,;:।!?()')]
    for width in range(1,9):
        for start in range(max(0,len(tokens)-4*width+1)):
            phrase=tokens[start:start+width]
            if not any(word not in FUNCTION_WORDS for word in phrase):continue
            if all(tokens[start+i*width:start+(i+1)*width]==phrase for i in range(1,4)):
                return True
    return False
