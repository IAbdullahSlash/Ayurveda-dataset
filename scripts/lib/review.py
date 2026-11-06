"""Review artifacts must not overwrite human annotations when regenerated."""
import pandas as pd

ANNOTATIONS = ('verdict','corrected_value','reviewer','reviewer_1','reviewer_2',
               'adjudicated_label','adjudicated_phrases','independent_case_unit')

def write_review_csv(frame, path):
    if path.exists():
        previous=pd.read_csv(path,keep_default_na=False)
        if any(previous[col].ne('').any() for col in ANNOTATIONS if col in previous):
            raise ValueError(f'Refusing to overwrite annotated review file: {path}')
    frame.to_csv(path,index=False)
