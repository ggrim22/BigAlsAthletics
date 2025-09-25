from io import BytesIO

from django.http import HttpResponse

import polars as pl
from xlsxwriter import Workbook


class ExcelDownloadResponse:
    """Returns an HttpResponse with an excel file attachment created from a
    polars dataframe.
    """

    def __new__(cls, dataframe: pl.DataFrame, file_name: str) -> HttpResponse:
        cls.dataframe = dataframe
        cls.file_name = file_name
        return cls._get_response(cls)

    def _get_buffer(self) -> BytesIO:
        buffer = BytesIO()
        with Workbook(buffer) as wb:
            self.dataframe.write_excel(wb, autofit=True)
        buffer.seek(0)
        return buffer

    def _get_response(self) -> HttpResponse:
        response = HttpResponse(
            self._get_buffer(self).read(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f"attachment; filename={self.file_name}.xlsx"
        return response
