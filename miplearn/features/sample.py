#  MIPLearn: Extensible Framework for Learning-Enhanced Mixed-Integer Optimization
#  Copyright (C) 2020-2021, UChicago Argonne, LLC. All rights reserved.
#  Released under the modified BSD license. See COPYING.md for more details.

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Dict, Optional, Any, Union, List, Tuple, cast, Set

import h5py
import numpy as np
from h5py import Dataset
from overrides import overrides

Scalar = Union[None, bool, str, int, float]
Vector = Union[
    None,
    List[bool],
    List[str],
    List[int],
    List[float],
    List[Optional[str]],
]
VectorList = Union[
    List[List[bool]],
    List[List[str]],
    List[List[int]],
    List[List[float]],
    List[Optional[List[bool]]],
    List[Optional[List[str]]],
    List[Optional[List[int]]],
    List[Optional[List[float]]],
]


class Sample(ABC):
    """Abstract dictionary-like class that stores training data."""

    @abstractmethod
    def get_scalar(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def put_scalar(self, key: str, value: Scalar) -> None:
        pass

    @abstractmethod
    def get_vector(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def put_vector(self, key: str, value: Vector) -> None:
        pass

    @abstractmethod
    def get_vector_list(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def put_vector_list(self, key: str, value: VectorList) -> None:
        pass

    def get_set(self, key: str) -> Set:
        v = self.get_vector(key)
        if v:
            return set(v)
        else:
            return set()

    def put_set(self, key: str, value: Set) -> None:
        v = list(value)
        self.put_vector(key, v)

    def _assert_is_scalar(self, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (str, bool, int, float)):
            return
        assert False, f"Scalar expected; found instead: {value}"

    def _assert_is_vector(self, value: Any) -> None:
        assert isinstance(value, list), f"List expected; found instead: {value}"
        for v in value:
            self._assert_is_scalar(v)

    def _assert_is_vector_list(self, value: Any) -> None:
        assert isinstance(value, list), f"List expected; found instead: {value}"
        for v in value:
            if v is None:
                continue
            self._assert_is_vector(v)


class MemorySample(Sample):
    """Dictionary-like class that stores training data in-memory."""

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if data is None:
            data = {}
        self._data: Dict[str, Any] = data

    @overrides
    def get_scalar(self, key: str) -> Optional[Any]:
        return self._get(key)

    @overrides
    def get_vector(self, key: str) -> Optional[Any]:
        return self._get(key)

    @overrides
    def get_vector_list(self, key: str) -> Optional[Any]:
        return self._get(key)

    @overrides
    def put_scalar(self, key: str, value: Scalar) -> None:
        self._assert_is_scalar(value)
        self._put(key, value)

    @overrides
    def put_vector(self, key: str, value: Vector) -> None:
        if value is None:
            return
        self._assert_is_vector(value)
        self._put(key, value)

    @overrides
    def put_vector_list(self, key: str, value: VectorList) -> None:
        self._assert_is_vector_list(value)
        self._put(key, value)

    def _get(self, key: str) -> Optional[Any]:
        if key in self._data:
            return self._data[key]
        else:
            return None

    def _put(self, key: str, value: Any) -> None:
        self._data[key] = value


class Hdf5Sample(Sample):
    """
    Dictionary-like class that stores training data in an HDF5 file.

    Unlike MemorySample, this class only loads to memory the parts of the data set that
    are actually accessed, and therefore it is more scalable.
    """

    def __init__(self, filename: str) -> None:
        self.file = h5py.File(filename, "r+")

    @overrides
    def get_scalar(self, key: str) -> Optional[Any]:
        ds = self.file[key]
        assert len(ds.shape) == 0
        if h5py.check_string_dtype(ds.dtype):
            return ds.asstr()[()]
        else:
            return ds[()].tolist()

    @overrides
    def get_vector(self, key: str) -> Optional[Any]:
        ds = self.file[key]
        assert len(ds.shape) == 1
        print(ds.dtype)
        if h5py.check_string_dtype(ds.dtype):
            return ds.asstr()[:].tolist()
        else:
            return ds[:].tolist()

    @overrides
    def get_vector_list(self, key: str) -> Optional[Any]:
        ds = self.file[key]
        lens = ds.attrs["lengths"]
        if h5py.check_string_dtype(ds.dtype):
            padded = ds.asstr()[:].tolist()
        else:
            padded = ds[:].tolist()
        return _crop(padded, lens)

    @overrides
    def put_scalar(self, key: str, value: Any) -> None:
        self._assert_is_scalar(value)
        self._put(key, value)

    @overrides
    def put_vector(self, key: str, value: Vector) -> None:
        if value is None:
            return
        self._assert_is_vector(value)
        self._put(key, value)

    @overrides
    def put_vector_list(self, key: str, value: VectorList) -> None:
        self._assert_is_vector_list(value)
        padded, lens = _pad(value)
        data = None
        for v in value:
            if v is None or len(v) == 0:
                continue
            if isinstance(v[0], str):
                data = np.array(padded, dtype="S")
            elif isinstance(v[0], bool):
                data = np.array(padded, dtype=bool)
            else:
                data = np.array(padded)
            break
        assert data is not None
        ds = self._put(key, data)
        ds.attrs["lengths"] = lens

    def _put(self, key: str, value: Any) -> Dataset:
        if key in self.file:
            del self.file[key]
        return self.file.create_dataset(key, data=value)


def _pad(veclist: VectorList) -> Tuple[VectorList, List[int]]:
    veclist = deepcopy(veclist)
    lens = [len(v) if v is not None else -1 for v in veclist]
    maxlen = max(lens)

    # Find appropriate constant to pad the vectors
    constant: Union[int, float, str, None] = None
    for v in veclist:
        if v is None or len(v) == 0:
            continue
        if isinstance(v[0], int):
            constant = 0
        elif isinstance(v[0], float):
            constant = 0.0
        elif isinstance(v[0], str):
            constant = ""
        else:
            assert False, f"Unsupported data type: {v[0]}"
    assert constant is not None, "veclist must not be completely empty"

    # Pad vectors
    for (i, vi) in enumerate(veclist):
        if vi is None:
            vi = veclist[i] = []
        assert isinstance(vi, list)
        for k in range(len(vi), maxlen):
            vi.append(constant)

    return veclist, lens


def _crop(veclist: VectorList, lens: List[int]) -> VectorList:
    result: VectorList = cast(VectorList, [])
    for (i, v) in enumerate(veclist):
        if lens[i] < 0:
            result.append(None)  # type: ignore
        else:
            assert isinstance(v, list)
            result.append(v[: lens[i]])
    return result