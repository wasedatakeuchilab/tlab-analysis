import io
import os
import typing as t
from unittest import mock

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from tlab_analysis import trpl

WAVELENGTH_RESOLUTION = 640
TIME_RESOLUTION = 480


@pytest.fixture()
def header() -> bytes:
    return bytes.fromhex(
        "49 4d cd 01 80 02 e0 01 00 00 00 00 02 00 00 00"
        "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
        "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
        "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    )


@pytest.fixture()
def metadata() -> str:
    metadata = (
        "HiPic,1.0,100,1.0,0,0,4,8,0,0,0,01-01-1970,00:00:00,"
        "0,0,0,0,0, , , , ,0,0,0,0,0, , ,0,, , , ,0,0,, ,0,0,0,0,0,0,0,0,0,0,"
        "2,1,nm,*0614925,2,1,ns,*0619021,0,0,0,0,0,0,0,0,0,2,0,0,0,0,0.0,0,0,"
        "StopCondition:PhotonCounting, Frame=10000, Time=673.1[sec], CountingRate=0.13[%]\n"
        "Streak:Time=10 ns, Mode=Operate, Shutter=0, MCPGain=12, MCPSwitch=1, \n"
        "Spectrograph:Wavelength=490.000[nm], Grating=2 : 150g/mm, SlitWidthIn=100[um], Mode=Spectrograph\n"
        "Date:2022/01/01,00:00:00\n"
    )
    return metadata


@pytest.fixture()
def streak_image() -> npt.NDArray[np.uint16]:
    random = np.random.RandomState(0)
    return random.randint(
        0, 64, WAVELENGTH_RESOLUTION * TIME_RESOLUTION, dtype=np.uint16
    )


@pytest.fixture()
def wavelength() -> npt.NDArray[np.float32]:
    return np.linspace(435, 535, WAVELENGTH_RESOLUTION, dtype=np.float32)


@pytest.fixture()
def time() -> npt.NDArray[np.float32]:
    return np.linspace(0, 10, TIME_RESOLUTION, dtype=np.float32)


@pytest.fixture()
def data(
    header: bytes,
    metadata: str,
    streak_image: npt.NDArray[np.uint16],
    wavelength: npt.NDArray[np.float32],
    time: npt.NDArray[np.float32],
) -> trpl.TRPLData:
    df = pd.DataFrame(
        dict(
            time=np.repeat(time, len(wavelength)),
            wavelength=np.tile(wavelength, len(time)),
            intensity=streak_image,
        )
    )
    data = trpl.TRPLData(df, header, metadata)
    return data


@pytest.fixture()
def raw_binary(
    header: bytes,
    metadata: str,
    streak_image: npt.NDArray[np.uint16],
    wavelength: npt.NDArray[np.float32],
    time: npt.NDArray[np.float32],
) -> bytes:
    u8167 = trpl.TRPLData.u8167()
    return (
        header
        + metadata.encode("UTF-8")
        + streak_image.astype(np.uint16).tobytes("C")
        + wavelength.tobytes("C").ljust(
            u8167.sector_size * u8167.num_sector_wavelength, b"\x00"
        )
        + time.tobytes("C").ljust(u8167.sector_size * u8167.num_sector_time, b"\x00")
    )


@pytest.fixture()
def write_raw_binary(filepath: os.PathLike[str], raw_binary: bytes) -> None:
    with open(filepath, "wb") as f:
        f.write(raw_binary)


@pytest.mark.parametrize("filename", ["photo_luminescence_testcase.img"])
@pytest.mark.usefixtures(write_raw_binary.__name__)
def test_read_img(filepath: os.PathLike[str], data: trpl.TRPLData) -> None:
    actual = trpl.read_img(filepath)
    assert actual == data


def test_read_img_from_buffer(raw_binary: bytes, data: trpl.TRPLData) -> None:
    with io.BytesIO(raw_binary) as f:
        actual = trpl.read_img(f)
    assert actual == data


def test_read_img_invalid_type() -> None:
    with pytest.raises(ValueError):
        trpl.read_img(None)  # type: ignore


def describe_trpl_data_frame() -> None:
    def test_time(data: trpl.TRPLData) -> None:
        pd.testing.assert_series_equal(data.time, data.df["time"])

    def test_wavelength(data: trpl.TRPLData) -> None:
        pd.testing.assert_series_equal(data.wavelength, data.df["wavelength"])

    def test_instensity(data: trpl.TRPLData) -> None:
        pd.testing.assert_series_equal(data.intensity, data.df["intensity"])

    def test_to_streak_image(
        data: trpl.TRPLData, streak_image: npt.NDArray[np.uint16]
    ) -> None:
        img = data.to_streak_image()
        assert img.shape == (TIME_RESOLUTION, WAVELENGTH_RESOLUTION)
        assert np.all(
            img
            == streak_image.astype(np.float32).reshape(
                TIME_RESOLUTION, WAVELENGTH_RESOLUTION
            ),
        )

    def test_to_raw_binary(data: trpl.TRPLData, raw_binary: bytes) -> None:
        assert data.to_raw_binary() == raw_binary

    @pytest.mark.parametrize("time_range", [None, (0.0, 1.0)])
    def test_aggregate_along_time(
        data: trpl.TRPLData, time_range: tuple[float, float] | None
    ) -> None:
        actual = data.aggregate_along_time(time_range)
        if time_range is None:
            time_range = data.time.min(), data.time.max()
        expected = (
            data.df[data.time.between(*time_range)]
            .groupby("wavelength")
            .sum()
            .drop("time", axis=1)
            .sort_values("wavelength")
            .reset_index()
        )
        assert actual.attrs["time_range"] == time_range
        pd.testing.assert_frame_equal(actual, expected)

    @pytest.mark.parametrize("wavelength_range", [None, (0.0, 1.0)])
    @pytest.mark.parametrize("time_offset", ["auto", 1.0])
    @pytest.mark.parametrize("intensity_offset", ["auto", 1.0])
    @mock.patch("tlab_analysis.utils.find_scdc", return_value=(0.0, 0.0))
    def test_aggregate_along_wavelength_with_wavelength_range(
        find_scdc_mock: mock.Mock,
        data: trpl.TRPLData,
        wavelength_range: tuple[float, float] | None,
        time_offset: t.Literal["auto"] | float,
        intensity_offset: t.Literal["auto"] | float,
    ) -> None:
        actual = data.aggregate_along_wavelength(
            wavelength_range, time_offset, intensity_offset
        )
        if wavelength_range is None:
            wavelength_range = data.wavelength.min(), data.wavelength.max()
        if time_offset == "auto":
            time_offset = float(find_scdc_mock.return_value[0])
        if intensity_offset == "auto":
            intensity_offset = float(find_scdc_mock.return_value[1])
        expected = (
            data.df[data.wavelength.between(*wavelength_range)]
            .groupby("time")
            .sum()
            .drop("wavelength", axis=1)
            .sort_values("time")
            .reset_index()
        )
        expected["time"] -= time_offset
        expected["intensity"] -= intensity_offset
        assert actual.attrs["wavelength_range"] == wavelength_range
        assert actual.attrs["time_offset"] == time_offset
        assert actual.attrs["intensity_offset"] == intensity_offset
        pd.testing.assert_frame_equal(actual, expected)
