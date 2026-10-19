import io
import zipfile

import pytest

from src import download_data, eda
from src.config import COLUMNS, EXPECTED_ROWS


def _csv_text(df):
    return df.to_csv(index=False, header=False)


@pytest.fixture()
def full_size_raw():
    from conftest import make_synthetic_heart
    return make_synthetic_heart(n=EXPECTED_ROWS)


@pytest.fixture()
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(download_data, "RAW_DATA_PATH", tmp_path / "raw.csv")
    monkeypatch.setattr(download_data, "save_clean", lambda: None)
    return tmp_path


class FakeResp:
    def __init__(self, text="", content=b""):
        self.text, self.content = text, content

    def raise_for_status(self):
        pass


def test_download_plain_csv(monkeypatch, isolated_paths, full_size_raw):
    monkeypatch.setattr(download_data, "DATA_URLS", ["http://x/processed.cleveland.data"])
    monkeypatch.setattr(download_data.requests, "get",
                        lambda url, timeout: FakeResp(text=_csv_text(full_size_raw)))
    df = download_data.download_dataset()
    assert df.shape == (EXPECTED_ROWS, len(COLUMNS))
    assert (isolated_paths / "raw.csv").exists()


def test_download_zip_fallback(monkeypatch, isolated_paths, full_size_raw):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("processed.cleveland.data", _csv_text(full_size_raw))

    def fake_get(url, timeout):
        if url.endswith(".zip"):
            return FakeResp(content=buf.getvalue())
        raise OSError("first mirror down")

    monkeypatch.setattr(download_data, "DATA_URLS", ["http://x/a.data", "http://x/b.zip"])
    monkeypatch.setattr(download_data.requests, "get", fake_get)
    assert download_data.download_dataset().shape[0] == EXPECTED_ROWS


def test_download_reuses_local_copy_when_offline(monkeypatch, isolated_paths, full_size_raw):
    full_size_raw.to_csv(isolated_paths / "raw.csv", index=False)
    monkeypatch.setattr(download_data.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert len(download_data.download_dataset()) == EXPECTED_ROWS


def test_download_fails_clearly_without_any_data(monkeypatch, isolated_paths):
    monkeypatch.setattr(download_data.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    with pytest.raises(SystemExit, match="Could not download"):
        download_data.download_dataset()


def test_download_rejects_wrong_shape(monkeypatch, isolated_paths, synthetic_raw):
    monkeypatch.setattr(download_data, "DATA_URLS", ["http://x/a.data"])
    monkeypatch.setattr(download_data.requests, "get",
                        lambda url, timeout: FakeResp(text=_csv_text(synthetic_raw)))
    with pytest.raises(SystemExit):
        download_data.download_dataset()


def test_eda_writes_all_plots(tmp_path, synthetic_raw):
    raw = tmp_path / "raw.csv"
    synthetic_raw.to_csv(raw, index=False)
    out = eda.perform_eda(raw, tmp_path / "clean.csv", tmp_path / "plots")
    assert len(out["plots"]) == 6
    names = {p.name for p in (tmp_path / "plots").iterdir()}
    assert {"class_balance.png", "feature_histograms.png", "correlation_heatmap.png",
            "summary_statistics.csv"} <= names
