from typing import Dict, Optional

import pandas as pd
import transformers
from huggingface_hub import HfApi

from mindsdb.integrations.handlers.huggingface_handler.settings import FINETUNE_MAP
from mindsdb.integrations.libs.base import BaseMLEngine
from mindsdb.utilities import log

logger = log.getLogger(__name__)


class HuggingFaceHandler(BaseMLEngine):
    name = "huggingface"

    @staticmethod
    def create_validation(target, args=None, **kwargs):
        if "using" in args:
            args = args["using"]

        hf_api = HfApi()

        # check model is pytorch based
        metadata = hf_api.model_info(args["model_name"])
        if "pytorch" not in metadata.tags:
            raise Exception(
                "Currently only PyTorch models are supported (https://huggingface.co/models?library=pytorch&sort=downloads). To request another library, please contact us on our community slack (https://mindsdb.com/joincommunity)."
            )

        # check model task
        supported_tasks = [
            "text-classification",
            "text-generation",
            "zero-shot-classification",
            "translation",
            "summarization",
            "text2text-generation",
            "fill-mask",
        ]

        if metadata.pipeline_tag not in supported_tasks:
            raise Exception(
                f"Not supported task for model: {metadata.pipeline_tag}.\
             Should be one of {', '.join(supported_tasks)}"
            )

        if "task" not in args:
            args["task"] = metadata.pipeline_tag
        elif args["task"] != metadata.pipeline_tag:
            raise Exception(f"Task mismatch for model: {args['task']}!={metadata.pipeline_tag}")

        input_keys = list(args.keys())

        # task, model_name, input_column is essential
        for key in ["task", "model_name", "input_column"]:
            if key not in args:
                raise Exception(f'Parameter "{key}" is required')
            input_keys.remove(key)

        # check tasks input

        if args["task"] == "zero-shot-classification":
            key = "candidate_labels"
            if key not in args:
                raise Exception('"candidate_labels" is required for zero-shot-classification')
            input_keys.remove(key)

        if args["task"] == "translation":
            keys = ["lang_input", "lang_output"]
            for key in keys:
                if key not in args:
                    raise Exception(f"{key} is required for translation")
                input_keys.remove(key)

        if args["task"] == "summarization":
            keys = ["min_output_length", "max_output_length"]
            for key in keys:
                if key not in args:
                    raise Exception(f"{key} is required for summarization")
                input_keys.remove(key)

        # optional keys
        for key in ["labels", "max_length", "truncation_policy"]:
            if key in input_keys:
                input_keys.remove(key)

        if len(input_keys) > 0:
            raise Exception(f"Not expected parameters: {', '.join(input_keys)}")

    def create(self, target, args=None, **kwargs):
        # TODO change BaseMLEngine api?
        if "using" in args:
            args = args["using"]

        args["target"] = target

        model_name = args["model_name"]
        hf_model_storage_path = self.engine_storage.folder_get(model_name)  # real

        if args["task"] == "translation":
            args["task_proper"] = f"translation_{args['lang_input']}_to_{args['lang_output']}"
        else:
            args["task_proper"] = args["task"]

        logger.debug(f"Checking file system for {model_name}...")

        ####
        # Check if pipeline has already been downloaded
        try:
            pipeline = transformers.pipeline(
                task=args["task_proper"], model=hf_model_storage_path, tokenizer=hf_model_storage_path
            )
            logger.debug("Model already downloaded!")
        ####
        # Otherwise download it
        except (ValueError, OSError):
            try:
                logger.debug(f"Downloading {model_name}...")
                pipeline = transformers.pipeline(task=args["task_proper"], model=model_name)

                pipeline.save_pretrained(hf_model_storage_path)

                logger.debug(f"Saved to {hf_model_storage_path}")
            except Exception:
                raise Exception(
                    "Error while downloading and setting up the model. Please try a different model. We're working on expanding the list of supported models, so we would appreciate it if you let us know about this in our community slack (https://mindsdb.com/joincommunity)."
                )  # noqa
        ####

        if "max_length" in args:
            pass
        elif "max_position_embeddings" in pipeline.model.config.to_dict().keys():
            args["max_length"] = pipeline.model.config.max_position_embeddings
        elif "max_length" in pipeline.model.config.to_dict().keys():
            args["max_length"] = pipeline.model.config.max_length
        else:
            logger.debug("No max_length found!")

        labels_default = pipeline.model.config.id2label
        labels_map = {}
        if "labels" in args:
            for num in labels_default.keys():
                labels_map[labels_default[num]] = args["labels"][num]
            args["labels_map"] = labels_map
        else:
            for num in labels_default.keys():
                labels_map[labels_default[num]] = labels_default[num]
            args["labels_map"] = labels_map

        # store and persist in model folder
        self.model_storage.json_set("args", args)

        # persist changes to handler folder
        self.engine_storage.folder_sync(model_name)

    # todo move infer tasks to a separate file
    def predict_text_classification(self, pipeline, item, args):
        top_k = args.get("top_k", 1000)

        result = pipeline([item], top_k=top_k, truncation=True, max_length=args["max_length"])[0]

        final = {}
        explain = {}
        if type(result) == dict:
            result = [result]
        final[args["target"]] = args["labels_map"][result[0]["label"]]
        for elem in result:
            if args["labels_map"]:
                explain[args["labels_map"][elem["label"]]] = elem["score"]
            else:
                explain[elem["label"]] = elem["score"]
        final[f"{args['target']}_explain"] = explain
        return final

    def predict_text_generation(self, pipeline, item, args):
        result = pipeline([item], max_length=args["max_length"])[0]

        final = {}
        final[args["target"]] = result["generated_text"]

        return final

    def predict_zero_shot(self, pipeline, item, args):
        top_k = args.get("top_k", 1000)

        result = pipeline(
            [item],
            candidate_labels=args["candidate_labels"],
            truncation=True,
            top_k=top_k,
            max_length=args["max_length"],
        )[0]

        final = {}
        final[args["target"]] = result["labels"][0]

        explain = dict(zip(result["labels"], result["scores"]))
        final[f"{args['target']}_explain"] = explain

        return final

    def predict_translation(self, pipeline, item, args):
        result = pipeline([item], max_length=args["max_length"])[0]

        final = {}
        final[args["target"]] = result["translation_text"]

        return final

    def predict_summarization(self, pipeline, item, args):
        result = pipeline(
            [item],
            min_length=args["min_output_length"],
            max_length=args["max_output_length"],
        )[0]

        final = {}
        final[args["target"]] = result["summary_text"]

        return final

    def predict_text2text(self, pipeline, item, args):
        result = pipeline([item], max_length=args["max_length"])[0]

        final = {}
        final[args["target"]] = result["generated_text"]

        return final

    def predict_fill_mask(self, pipeline, item, args):
        result = pipeline([item])[0]

        final = {}
        final[args["target"]] = result[0]["sequence"]
        explain = {elem["sequence"]: elem["score"] for elem in result}
        final[f"{args['target']}_explain"] = explain

        return final

    def predict(self, df, args=None):
        fnc_list = {
            "text-classification": self.predict_text_classification,
            "text-generation": self.predict_text_generation,
            "zero-shot-classification": self.predict_zero_shot,
            "translation": self.predict_translation,
            "summarization": self.predict_summarization,
            "fill-mask": self.predict_fill_mask,
        }

        # get stuff from model folder
        args = self.model_storage.json_get("args")

        task = args["task"]

        if task not in fnc_list:
            raise RuntimeError(f"Unknown task: {task}")

        fnc = fnc_list[task]

        try:
            # load from model storage (finetuned models will use this)
            hf_model_storage_path = self.model_storage.folder_get(args["model_name"])
            pipeline = transformers.pipeline(
                task=args["task_proper"],
                model=hf_model_storage_path,
                tokenizer=hf_model_storage_path,
            )
        except (ValueError, OSError):
            # load from engine storage (i.e. 'common' models)
            hf_model_storage_path = self.engine_storage.folder_get(args["model_name"])
            pipeline = transformers.pipeline(
                task=args["task_proper"],
                model=hf_model_storage_path,
                tokenizer=hf_model_storage_path,
            )

        input_column = args["input_column"]
        if input_column not in df.columns:
            raise RuntimeError(f'Column "{input_column}" not found in input data')
        input_list = df[input_column]

        max_tokens = pipeline.tokenizer.model_max_length

        results = []
        for item in input_list:
            if max_tokens is not None:
                tokens = pipeline.tokenizer.encode(item)
                if len(tokens) > max_tokens:
                    truncation_policy = args.get("truncation_policy", "strict")
                    if truncation_policy == "strict":
                        results.append({"error": f"Tokens count exceed model limit: {len(tokens)} > {max_tokens}"})
                        continue
                    elif truncation_policy == "left":
                        tokens = tokens[-max_tokens + 1 : -1]  # cut 2 empty tokens from left and right
                    else:
                        tokens = tokens[1 : max_tokens - 1]  # cut 2 empty tokens from left and right

                    item = pipeline.tokenizer.decode(tokens)

            item = str(item)
            try:
                result = fnc(pipeline, item, args)
            except Exception as e:
                msg = str(e).strip()
                if msg == "":
                    msg = e.__class__.__name__
                result = {"error": msg}
            results.append(result)

        pred_df = pd.DataFrame(results)

        return pred_df

    def describe(self, attribute: Optional[str] = None) -> pd.DataFrame:
        args = self.model_storage.json_get("args")
        if attribute == "args":
            return pd.DataFrame(args.items(), columns=["key", "value"])
        elif attribute == "metadata":
            hf_api = HfApi()
            metadata = hf_api.model_info(args["model_name"])
            data = metadata.__dict__
            return pd.DataFrame(list(data.items()), columns=["key", "value"])
        else:
            tables = ["args", "metadata"]
            return pd.DataFrame(tables, columns=["tables"])

    def finetune(self, df: Optional[pd.DataFrame] = None, args: Optional[Dict] = None) -> None:
        finetune_args = args if args else {}
        args = self.base_model_storage.json_get("args")
        args.update(finetune_args)

        model_name = args["model_name"]
        model_folder = self.model_storage.folder_get(model_name)
        args["model_folder"] = model_folder
        model_folder_name = model_folder.split("/")[-1]
        task = args["task"]

        if task not in FINETUNE_MAP:
            raise KeyError(
                f"{task} is not currently supported, please choose a supported task - {', '.join(FINETUNE_MAP)}"
            )

        tokenizer, trainer = FINETUNE_MAP[task](df, args)

        try:
            trainer.train()
            trainer.save_model(
                model_folder
            )  # TODO: save entire pipeline instead https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.Pipeline.save_pretrained
            tokenizer.save_pretrained(model_folder)

            # persist changes
            self.model_storage.json_set("args", args)
            self.model_storage.folder_sync(model_folder_name)

        except Exception as e:
            err_str = f"Finetune failed with error: {str(e)}"
            logger.debug(err_str)
            raise Exception(err_str)
