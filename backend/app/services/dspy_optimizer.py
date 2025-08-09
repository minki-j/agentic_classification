import time
import dspy
import os
import json
from typing import List, Any
from enum import Enum
from datetime import datetime
from app.websocket.manager import ConnectionManager

COMPILED_MODULE_ROOT_PATH = "app/services/compiled_dspy_modules/"


class DspyOptimizer(dspy.Module):
    def __init__(
        self,
        lm: dspy.LM,
        connection_manager: ConnectionManager,
        user_id: str,
        node_id: str,
        categories: List[str],
        trainset: List[dspy.Example],
        callbacks: List[Any] = [],
        metric_threshold: float = 0.99,
        max_bootstrapped_demos: int = 10,
        max_labeled_demos: int = 0,
        max_rounds: int = 1,
    ):
        super().__init__()
        self.compiled_module_root_path = COMPILED_MODULE_ROOT_PATH
        self.lm = lm
        self.connection_manager = connection_manager
        self.user_id = user_id
        self.node_id = node_id
        self.categories = categories
        self.trainset = trainset
        self.callbacks = callbacks if callbacks is not None else []
        self.max_bootstrapped_demos = max_bootstrapped_demos
        self.metric_threshold = metric_threshold
        self.max_rounds = max_rounds
        self.max_labeled_demos = max_labeled_demos

    def _create_signature(self, categories: List[str]):
        # Create a dynamic signature class with the categories
        class ClassificationResult(dspy.Signature):
            """Classify a review into one of the predefined categories."""

            review: str = dspy.InputField(desc="The review text to classify")
            category: str = dspy.OutputField(
                desc=f"The category of the review. One of {categories}"
            )

        return ClassificationResult

    def _metric_function(self, ground_truth, prediction, trace=None):
        # Check if the predicted category matches the ground truth
        pred_category = prediction.get("category", None)
        gt_category = ground_truth.get("category", None)
        # print(f"\n\n\n\n\npred_category: {pred_category}, gt_category: {gt_category}")
        # print(
        #     f"score: {(pred_category.lower().strip() == gt_category.lower().strip())}"
        # )

        if pred_category is None or gt_category is None:
            raise ValueError(
                f"Prediction or ground truth category is None: {prediction} {ground_truth}"
            )

        return (
            1 if (pred_category.lower().strip() == gt_category.lower().strip()) else 0
        )

    async def compile(self):
        # Compile returns the optimized module

        dspy.configure(lm=self.lm, callbacks=self.callbacks)

        signature = self._create_signature(self.categories)

        student = dspy.Predict(signature)

        bootstrap_module = dspy.BootstrapFewShot(
            metric=self._metric_function,
            metric_threshold=self.metric_threshold,
            teacher_settings=None,
            max_bootstrapped_demos=self.max_bootstrapped_demos,
            max_labeled_demos=self.max_labeled_demos,  # number of fewshot examples in each llm call
            max_rounds=self.max_rounds,  # how many times to run the same llm calls
            max_errors=1,
        )

        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"DSPy optimizer module_id: {current_time}")

        await self.connection_manager.send_dspy_update(
            user_id=self.user_id,
            data={
                "message": f"Start optimizing few-shot with {len(self.trainset)} examples! Will send you a notification when it's done!",
                "compiled_module_id": current_time,
            },
        )

        start_time = time.time()
        compiled_classifier = bootstrap_module.compile(
            student=student, trainset=self.trainset
        )
        end_time = time.time()
        print(f"DSPy compile took {end_time - start_time:.2f} seconds")

        if end_time - start_time < 120:
            time.sleep(120 - (end_time - start_time))

        compiled_classifier.save(
            os.path.join(self.compiled_module_root_path, current_time + ".json")
        )
        await self.connection_manager.send_dspy_update(
            user_id=self.user_id,
            data={
                "message": f"Selected {len(self.trainset)} few shot examples.",
                "compiled_module_id": current_time,
                "demos": return_demos(current_time),
                "node_id": self.node_id,
            },
        )
        return current_time

    async def predict(
        self,
        review: str,
        compiled_module_id: str,
    ):
        dspy.configure(lm=self.lm, callbacks=self.callbacks)

        signature = self._create_signature(self.categories)
        classifier = dspy.Predict(signature)

        classifier.load(
            os.path.join(self.compiled_module_root_path, compiled_module_id + ".json")
        )

        return classifier(review=review)


def return_demos(compiled_module_id: str) -> List[str]:
    with open(
        os.path.join(COMPILED_MODULE_ROOT_PATH, compiled_module_id + ".json"),
        "r",
    ) as f:
        compiled_module = json.load(f)

    demos = []
    for demo in compiled_module["demos"]:
        demos.append(demo["review"])

    return demos
