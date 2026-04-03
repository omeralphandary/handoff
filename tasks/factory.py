"""Build task list from zone task_types strings."""
from __future__ import annotations
from tasks.base import BaseTask
from tasks.documentation import DocumentationTask
from tasks.ocr import OCRTask
from tasks.inspection import InspectionTask
from tasks.classification import ClassificationTask
from vlm.client import BaseVLMClient


def build_tasks(task_types: list[str], vlm: BaseVLMClient, store) -> list[BaseTask]:
    tasks: list[BaseTask] = []
    for t in task_types:
        if t == "documentation":
            tasks.append(DocumentationTask(vlm, store))
        elif t == "ocr":
            tasks.append(OCRTask(vlm, store))
        elif t == "inspection":
            tasks.append(InspectionTask(vlm, store))
        elif t == "classification":
            tasks.append(ClassificationTask(vlm, store))
    return tasks
