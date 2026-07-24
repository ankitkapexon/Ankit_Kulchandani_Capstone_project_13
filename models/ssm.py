from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ElementType(str, Enum):
    textfield = "textfield"
    button = "button"
    image = "image"
    label = "label"
    checkbox = "checkbox"
    dropdown = "dropdown"
    link = "link"
    unknown = "unknown"
    search_field = "search_field"
    list = "list"
    icon_button = "icon_button"
    stepper = "stepper"
    text = "text"


class ElementAction(str, Enum):
    enter_text = "enter_text"
    tap = "tap"
    verify = "verify"
    select = "select"
    swipe = "swipe"
    scroll = "scroll"
    long_press = "long_press"
    view = "view"
    view_items = "view_items"
    increase = "increase"
    decrease = "decrease"


class ScreenElement(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    type: str = "unknown"
    actions: List[str] = Field(default_factory=list)
    bbox: Optional[Dict[str, int]] = None  # {x, y, width, height} if available
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    def normalize_label(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "label" in values:
                label = values.get("label")
                if isinstance(label, str):
                    values["label"] = label.strip()
            if "type" in values and values.get("type") is None:
                values["type"] = "unknown"
            if "actions" in values and values.get("actions") is None:
                values["actions"] = []
        return values


class ScreenSemanticModel(BaseModel):
    screen_name: Optional[str] = None
    screen_purpose: Optional[str] = None
    source: Optional[str] = None
    source_image: Optional[str] = None
    elements: List[ScreenElement] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# helper to expose JSON Schema
def json_schema() -> Dict[str, Any]:
    return ScreenSemanticModel.model_json_schema()
