import numpy as np
import pandas as pd
import pytest

from src.config import COLUMNS, FEATURES
from src.data_processing import (build_preprocessor, clean_dataframe, feature_names,
                                 load_clean, load_raw, save_clean, split_xy)


def test_clean_binarises_target(synthetic_raw):
    clean = clean_dataframe(synthetic_raw)
    assert set(clean["target"].unique()) <= {0, 1}
    assert ((synthetic_raw["target"] > 0).astype(int) == clean["target"]).all()


def test_clean_handles_question_marks_and_junk(tmp_path):
    csv = tmp_path / "raw.csv"
    row = "63,1,1,145,233,1,2,150,0,2.3,3,?,6,0\n"
    csv.write_text(",".join(COLUMNS) + "\n" + row + row.replace("63", "64"))
    clean = clean_dataframe(load_raw(csv))
    assert clean["ca"].isna().all()
    assert clean.dtypes.map(lambda d: np.issubdtype(d, np.number)).all()


def test_clean_drops_duplicates(synthetic_raw):
    doubled = pd.concat([synthetic_raw, synthetic_raw.iloc[:10]])
    assert len(clean_dataframe(doubled)) == len(clean_dataframe(synthetic_raw))


def test_clean_rejects_missing_columns(synthetic_raw):
    with pytest.raises(ValueError, match="Missing expected columns"):
        clean_dataframe(synthetic_raw.drop(columns=["chol"]))


def test_clean_rejects_missing_target(synthetic_raw):
    bad = synthetic_raw.copy()
    bad.loc[0, "target"] = np.nan
    with pytest.raises(ValueError, match="Target"):
        clean_dataframe(bad)


def test_save_and_load_clean_roundtrip(tmp_path, synthetic_raw):
    raw = tmp_path / "raw.csv"
    synthetic_raw.to_csv(raw, index=False)
    saved = save_clean(raw, tmp_path / "clean.csv")
    loaded = load_clean(tmp_path / "clean.csv", raw)
    pd.testing.assert_frame_equal(saved, loaded, check_dtype=False)


def test_split_xy_shapes(synthetic_raw):
    X, y = split_xy(clean_dataframe(synthetic_raw))
    assert list(X.columns) == FEATURES and len(X) == len(y)


def test_preprocessor_imputes_scales_and_encodes(synthetic_raw):
    X, _ = split_xy(clean_dataframe(synthetic_raw))
    assert X.isna().any().any()                      # fixture really has gaps
    pre = build_preprocessor()
    out = pre.fit_transform(X)
    assert not np.isnan(out).any()
    assert out.shape[1] == len(feature_names(pre)) > len(FEATURES)
    numeric_block = out[:, :5]                        # scaled numeric columns come first
    assert np.allclose(numeric_block.mean(axis=0), 0, atol=1e-6)
    assert np.allclose(numeric_block.std(axis=0), 1, atol=1e-6)


def test_preprocessor_ignores_unseen_category(synthetic_raw):
    X, _ = split_xy(clean_dataframe(synthetic_raw))
    pre = build_preprocessor().fit(X)
    odd = X.iloc[:1].copy()
    odd["cp"] = 99.0
    assert pre.transform(odd).shape[0] == 1          # no exception thanks to handle_unknown
