from laf import candidates as K

HEADER = "time,latitude,longitude,depth,mag,magType,net,id,updated,place,type,status\n"


def _csv(rows):
    return (HEADER + "".join(f"{t},{la},{lo},10,{m},mw,us,{i},{t},somewhere,earthquake,reviewed\n"
                             for t, la, lo, m, i in rows)).encode()  # fmt: skip


def test_supplementary_candidates_drop_development_and_aftershocks_only(tmp_path, monkeypatch):
    from laf import candidates

    monkeypatch.setattr(candidates, "development_ids", lambda: frozenset({"usdev0001"}))
    window = [
        ("2026-10-30T00:00:00Z", 10.0, 120.0, 5.1, "usaft0001"),  # inside the M6.5's circle
        ("2026-10-31T00:00:00Z", 30.0, 140.0, 5.0, "usnew0001"),  # a new sequence
        ("2026-11-01T00:00:00Z", 40.0, 150.0, 5.2, "usdev0001"),  # development: never
        ("2026-11-02T00:00:00Z", 50.0, 160.0, 4.4, "usfwd0001"),  # a larger event follows
    ]
    later_big = ("2026-11-03T00:00:00Z", 50.01, 160.0, 6.0, "usbig0002")
    earlier_big = ("2026-09-01T00:00:00Z", 10.01, 120.0, 6.5, "usbig0001")

    def get(url):
        if "producttype=oaf" not in url:
            return _csv([])  # ComCat M>=6 context: none beyond the OAF events here
        if "starttime=2026-10-29" in url:
            return _csv([*window, later_big])
        return _csv([earlier_big, *window, later_big])  # the OAF context, a year back

    sel = K.select(tmp_path, "2026-10-29", "2026-11-04", get)
    # the forward half is not applied: usfwd0001 stays although usbig0002 follows it
    assert set(sel["id"]) == {"usnew0001", "usfwd0001", "usbig0002"}
    out = tmp_path / "supp.toml"
    K.write_config(sel, out, "2026-10-29", "2026-11-04")
    assert out.read_text().count("[[sequence]]") == 3
