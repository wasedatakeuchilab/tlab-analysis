from __future__ import annotations

import dataclasses
import io
import os
import typing as t
import warnings

import numpy as np
import numpy.typing as npt
import pandas as pd

from tlab_analysis import utils

DEFAULT_HEADER = bytes.fromhex(
    "49 4d cd 01 80 02 e0 01 00 00 00 00 02 00 00 00"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
)
DEFAULT_METADATA = [
    "HiPic,1.0,100,1.0,0,0,4,8,0,0,0,01-01-1970,00:00:00,"
    "0,0,0,0,0, , , , ,0,0,0,0,0, , ,0,, , , ,0,0,, ,0,0,0,0,0,0,0,0,0,0,2,"
    "1,nm,*0614925,2,1,ns,*0619021,0,0,0,0,0,0,0,0,0,2,0,0,0,0,0.0,0,0,"
    "StopCondition:PhotonCounting, Frame=10000, Time=300.0[sec], CountingRate=0.10[%]\n",
    "Streak:Time=10 ns, Mode=Operate, Shutter=0, MCPGain=10, MCPSwitch=1,\n",
    "Spectrograph:Wavelength=490.000[nm], Grating=2 : 150g/mm, SlitWidthIn=100[um], Mode=Spectrograph\n",
    "Date:1970/01/01,00:00:00\n",
]


def read_file(
    filepath_or_buffer: str | os.PathLike[str] | io.BufferedIOBase,
) -> TRPLData:
    """
    Reads and parses a raw binary file generated by u8167 application.

    Parameters
    ----------
    filepath_or_buffer : str | os.PathLike[str] | io.BufferedIOBase
        The path to a raw binary or buffer from u8167.

    Returns
    -------
    tlab_analysis.trpl.TRPLDataFrame
        A dataframe from the raw file.

    Raises
    ------
    ValueError
        If `filepath_or_buffer` is invalid.

    Examples
    --------
    >>> data = read_file("data.img")  # doctest: +SKIP
    """
    if isinstance(filepath_or_buffer, (str, os.PathLike)):
        with open(filepath_or_buffer, "rb") as f:
            return _read_file(f)
    elif isinstance(filepath_or_buffer, io.BufferedIOBase):
        return _read_file(filepath_or_buffer)
    else:
        raise ValueError(
            "The type of filepath_or_buffer must be os.PathLike or io.BufferedIOBase"
        )


def _read_file(file: io.BufferedIOBase) -> TRPLData:
    u8167 = TRPLData.u8167
    header = file.read(64)
    metadata = [file.readline().decode(u8167.encoding) for _ in range(4)]
    intensity = np.frombuffer(file.read(u8167.sector_size * 600), dtype=np.uint16)
    wavelength = np.frombuffer(file.read(u8167.sector_size * 4), dtype=np.float32)[
        : u8167.wavelength_resolution
    ]
    time = np.frombuffer(file.read(u8167.sector_size * 4), dtype=np.float32)[
        : u8167.time_resolution
    ]
    df = pd.DataFrame(
        dict(
            time=np.repeat(time, len(wavelength)),  # [ns]
            wavelength=np.tile(wavelength, len(time)),  # [nm]
            intensity=intensity,  # [arb. units]
        )
    )
    data = TRPLData(df, header, metadata)
    return data


def read_img(filepath_or_buffer: os.PathLike[str] | io.BufferedIOBase) -> TRPLData:
    """
    Reads and parses a raw binary file generated by u8167 application.

    Parameters
    ----------
    filepath_or_buffer : os.PathLike[str] | io.BufferedIOBase
        The path to a raw binary or buffer from u8167.

    Returns
    -------
    tlab_analysis.trpl.TRPLData
        A TRPLData object from the file.

    Raises
    ------
    ValueError
        If `filepath_or_buffer` is invalid.

    Examples
    --------
    >>> data = read_img("data.img")  # doctest: +SKIP
    """
    warnings.warn(
        f"{read_img.__name__} is deprecated and will be removed after version 0.4.0. "
        f"Use {read_file.__name__} instead.",
        stacklevel=2,
    )
    return read_file(filepath_or_buffer)


@dataclasses.dataclass(frozen=True)
class TRPLData:
    """
    Data class for time-resolved photo luminescence measurements.

    Examples
    --------
    Create dataframe of data.
    >>> time = np.linspace(0, 10, 3, dtype=np.float32)
    >>> wavelength = np.linspace(400, 500, 3, dtype=np.float32)
    >>> np.random.seed(0)
    >>> intensity = np.random.randint(0, 100, len(time) * len(wavelength))
    >>> df = pd.DataFrame(
    ...     dict(
    ...         time=np.repeat(time, len(wavelength)),
    ...         wavelength=np.tile(wavelength, len(time)),
    ...         intensity=intensity,
    ...     )
    ... )

    Create a TRPLData object.
    >>> data = TRPLData(df)
    >>> data.df
       time  wavelength  intensity
    0   0.0       400.0         44
    1   0.0       450.0         47
    2   0.0       500.0         64
    3   5.0       400.0         67
    4   5.0       450.0         67
    5   5.0       500.0          9
    6  10.0       400.0         83
    7  10.0       450.0         21
    8  10.0       500.0         36

    Access each column.
    >>> data.time
    0     0.0
    1     0.0
    2     0.0
    3     5.0
    4     5.0
    5     5.0
    6    10.0
    7    10.0
    8    10.0
    Name: time, dtype: float32
    >>> data.wavelength
    0    400.0
    1    450.0
    2    500.0
    3    400.0
    4    450.0
    5    500.0
    6    400.0
    7    450.0
    8    500.0
    Name: wavelength, dtype: float32
    >>> data.intensity
    0    44
    1    47
    2    64
    3    67
    4    67
    5     9
    6    83
    7    21
    8    36
    Name: intensity, dtype: int64

    Get the streak image.
    >>> data.to_streak_image()
    array([[44., 47., 64.],
           [67., 67.,  9.],
           [83., 21., 36.]], dtype=float32)

    Aggregate along each axis.
    >>> data.aggregate_along_time()
       wavelength  intensity
    0       400.0        194
    1       450.0        135
    2       500.0        109
    >>> data.aggregate_along_wavelength(time_offset=0, intensity_offset=0)
       time  intensity
    0   0.0        155
    1   5.0        143
    2  10.0        140

    Notes
    -----
    This class depends heavly on u8167 data structure.
    If you update your measurement system, this class can be deprecated.
    """

    df: pd.DataFrame
    """A dataframe of the measurement."""
    header: bytes = DEFAULT_HEADER
    """Bytes of the header of a raw binary from u8167."""
    metadata: list[str] = dataclasses.field(
        default_factory=lambda: list(DEFAULT_METADATA)
    )
    """Meta information of the data from u8167."""

    @dataclasses.dataclass(frozen=True)
    class u8167:
        encoding: str = "UTF-8"
        sector_size: int = 1024
        wavelength_resolution: int = 640
        time_resolution: int = 480
        num_sector_intensity: int = 600
        num_sector_wavelength: int = 4
        num_sector_time: int = 4

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, TRPLData):
            return all(
                (
                    (self.df == __o.df).all(axis=None),
                    self.header == __o.header,
                    self.metadata == __o.metadata,
                )
            )
        else:
            return NotImplemented  # pragma: no cover

    @property
    def time(self) -> pd.Series[t.Any]:
        """
        A series of time in nanosecond.
        """
        column_name = "time"
        assert (
            column_name in self.df.columns
        ), f"The column named `{column_name}` doesn't exist"
        return self.df[column_name]

    @property
    def wavelength(self) -> pd.Series[t.Any]:
        """
        A series of wavelength in nanometer.
        """
        column_name = "wavelength"
        assert (
            column_name in self.df.columns
        ), f"The column named `{column_name}` doesn't exist"
        return self.df[column_name]

    @property
    def intensity(self) -> pd.Series[t.Any]:
        """
        A series of intensity in arbitrary units.
        """
        column_name = "intensity"
        assert (
            column_name in self.df.columns
        ), f"The column named `{column_name}` doesn't exist"
        return self.df[column_name]

    def to_streak_image(self) -> npt.NDArray[np.float32]:
        """
        Returns a 2D array of the streak image.

        Returns
        -------
        numpy.ndarray[np.float32]
            A 2D array of the streak image.

        Examples
        --------
        >>> data = getfixture("trpl_data")
        >>> data.df
           time  wavelength  intensity
        0   0.0       400.0         44
        1   0.0       450.0         47
        2   0.0       500.0         64
        3   5.0       400.0         67
        4   5.0       450.0         67
        5   5.0       500.0          9
        6  10.0       400.0         83
        7  10.0       450.0         21
        8  10.0       500.0         36

        >>> data.to_streak_image()
        array([[44., 47., 64.],
               [67., 67.,  9.],
               [83., 21., 36.]], dtype=float32)
        """
        img = (
            self.df.sort_values(["time", "wavelength"])["intensity"]
            .to_numpy(dtype=np.float32)
            .reshape(len(self.time.unique()), len(self.wavelength.unique()))
        )
        return img

    def to_raw_binary(self) -> bytes:
        """
        Converts to a raw binary that u8167 can operate.

        Returns
        -------
        bytes
            A raw binary that u8167 can operate.
        """
        u8167 = self.u8167()
        intensity_size = u8167.sector_size * u8167.num_sector_intensity
        wavelength_size = u8167.sector_size * u8167.num_sector_wavelength
        time_size = u8167.sector_size * u8167.num_sector_time
        raw_binary = (
            self.header
            + "".join(self.metadata).encode(u8167.encoding)
            + self.intensity.to_numpy(np.uint16)
            .tobytes("C")
            .ljust(intensity_size, b"\x00")[:intensity_size]
            + self.wavelength.unique()
            .astype(np.float32)
            .tobytes("C")
            .ljust(wavelength_size, b"\x00")[:wavelength_size]
            + self.time.unique()
            .astype(np.float32)
            .tobytes("C")
            .ljust(time_size, b"\x00")[:time_size]
        )
        return raw_binary

    def aggregate_along_time(
        self, time_range: tuple[float, float] | None = None
    ) -> pd.DataFrame:
        """
        Aggregates data along the time axis.

        Parameters
        ----------
        time_range : tuple[float, float] | None
            A range of time for aggregation.
            If None, the whole time of data is used.

        Returns
        -------
        pandas.DataFrame
            A time-aggregated dataframe.

        Examples
        --------
        >>> data = getfixture("trpl_data")
        >>> data.df
           time  wavelength  intensity
        0   0.0       400.0         44
        1   0.0       450.0         47
        2   0.0       500.0         64
        3   5.0       400.0         67
        4   5.0       450.0         67
        5   5.0       500.0          9
        6  10.0       400.0         83
        7  10.0       450.0         21
        8  10.0       500.0         36

        >>> data.aggregate_along_time()
           wavelength  intensity
        0       400.0        194
        1       450.0        135
        2       500.0        109
        """
        if time_range is None:
            time_range = self.time.min(), self.time.max()
        df = (
            self.df[self.time.between(*time_range)]
            .groupby("wavelength")
            .sum()
            .drop("time", axis=1)
            .sort_values("wavelength")
            .reset_index()
        )
        df.attrs.update(time_range=time_range)
        return df

    def aggregate_along_wavelength(
        self,
        wavelength_range: tuple[float, float] | None = None,
        time_offset: t.Literal["auto"] | float = "auto",
        intensity_offset: t.Literal["auto"] | float = "auto",
    ) -> pd.DataFrame:
        """
        Aggregates data along the wavelength axis.

        Parameters
        ----------
        wavelength_range : tuple[float, float] | None
            A range of wavelength for aggregation.
            If None, the whole wavelength of data is used.
        time_offset : "auto" | float
            An offset value of time.
            `auto` will work if the intensity is a decay curve.
        intensity_offset : "auto" | float
            An offset value of intensity.
            `auto` will work if the intensity is a decay curve.

        Returns
        -------
        pandas.DataFrame
            A wavelength-aggregated dataframe.

        Examples
        --------
        >>> data = getfixture("trpl_data")
        >>> data.df
           time  wavelength  intensity
        0   0.0       400.0         44
        1   0.0       450.0         47
        2   0.0       500.0         64
        3   5.0       400.0         67
        4   5.0       450.0         67
        5   5.0       500.0          9
        6  10.0       400.0         83
        7  10.0       450.0         21
        8  10.0       500.0         36

        >>> data.aggregate_along_wavelength(time_offset=0, intensity_offset=0)
           time  intensity
        0   0.0        155
        1   5.0        143
        2  10.0        140
        """
        if wavelength_range is None:
            wavelength_range = self.wavelength.min(), self.wavelength.max()
        df = (
            self.df[self.wavelength.between(*wavelength_range)]
            .groupby("time")
            .sum()
            .drop("wavelength", axis=1)
            .sort_values("time")
            .reset_index()
        )
        if time_offset == "auto" or intensity_offset == "auto":
            scdc = utils.find_scdc(
                df["time"].to_list(),
                df["intensity"].to_list(),
            )
            time_offset = scdc[0] if time_offset == "auto" else time_offset
            intensity_offset = (
                scdc[1] if intensity_offset == "auto" else intensity_offset
            )
        df["time"] -= time_offset
        df["intensity"] -= intensity_offset
        df.attrs.update(
            wavelength_range=wavelength_range,
            time_offset=time_offset,
            intensity_offset=intensity_offset,
        )
        return df
