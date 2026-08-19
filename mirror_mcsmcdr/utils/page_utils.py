from enum import Enum
from typing import Any, List, Union

from mcdreforged.api.all import CommandContext, RAction, RTextList

from mirror_mcsmcdr.utils.display_utils import rtr


class PageValidationError(Enum):
    INVALID = "page_error"
    OUT_OF_INDEX = "page_outofindex"
    NO_DATA = "nodata"


class Page:
    def __init__(self, items: List[Any], page_size: int, command: str) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be greater than 0")
        self.items = items
        self.page_size = page_size
        self.total_pages = (len(items) + page_size - 1) // page_size
        self.current_page: Union[PageValidationError, int] = (
            PageValidationError.NO_DATA if self.total_pages == 0 else 1
        )
        self.command = command

    def set_page_index(self, context: CommandContext) -> bool:
        if "page" not in context.keys():
            return self.total_pages > 0
        page_str = context["page"]
        if not page_str.isdigit():
            self.current_page = PageValidationError.INVALID
            return False
        page = int(page_str)
        if page < 1 or page > self.total_pages:
            self.current_page = PageValidationError.OUT_OF_INDEX
            return False
        self.current_page = page
        return True

    def get_items_on_page(self) -> List[Any]:
        if isinstance(self.current_page, PageValidationError):
            return []
        start = (self.current_page - 1) * self.page_size
        return self.items[start:start + self.page_size]

    def get_rtext(self):
        page = self.current_page
        if isinstance(page, PageValidationError):
            return rtr(f"page.{page.value}", title=False)
        previous = rtr("page.pre", title=False).h(rtr("page.end_prompt" if page == 1 else "page.pre_prompt", title=False))
        if page != 1:
            previous = previous.c(RAction.run_command, f"{self.command} {page - 1}")
        next_page = rtr("page.next", title=False).h(rtr("page.end_prompt" if page == self.total_pages else "page.next_prompt", title=False))
        if page != self.total_pages:
            next_page = next_page.c(RAction.run_command, f"{self.command} {page + 1}")
        return RTextList(
            rtr("page.left", title=False),
            previous,
            rtr("page.page", title=False, current=page, total=self.total_pages),
            next_page,
            rtr("page.right", title=False),
        )
