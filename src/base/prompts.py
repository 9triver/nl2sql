import json
from typing import Union

from agno.utils.log import log_warning
from pydantic import BaseModel


def get_json_output_prompt(response_model: Union[str, list, BaseModel]) -> str:
    """Return the JSON output prompt for the Agent.

    This is added to the system prompt when the response_model is set and structured_outputs is False.
    """

    json_output_prompt = "请按照以下字段结构以JSON格式提供输出："
    if response_model is not None:
        if isinstance(response_model, str):
            json_output_prompt += "\n<json_fields>"
            json_output_prompt += f"\n{response_model}"
            json_output_prompt += "\n</json_fields>"
        elif isinstance(response_model, list):
            json_output_prompt += "\n<json_fields>"
            json_output_prompt += (
                f"\n{json.dumps(obj=response_model, ensure_ascii=False, indent=2)}"
            )
            json_output_prompt += "\n</json_fields>"
        elif (
            issubclass(type(response_model), BaseModel)
            or issubclass(response_model, BaseModel)  # type: ignore
            or isinstance(response_model, BaseModel)
        ):  # type: ignore
            json_schema = response_model.model_json_schema()
            if json_schema is not None:
                response_model_properties = {}
                json_schema_properties = json_schema.get("properties")
                if json_schema_properties is not None:
                    for field_name, field_properties in json_schema_properties.items():
                        formatted_field_properties = {
                            prop_name: prop_value
                            for prop_name, prop_value in field_properties.items()
                            if prop_name != "title"
                        }
                        # Handle enum references
                        if "allOf" in formatted_field_properties:
                            ref = formatted_field_properties["allOf"][0].get("$ref", "")
                            if ref.startswith("#/$defs/"):
                                enum_name = ref.split("/")[-1]
                                formatted_field_properties["enum_type"] = enum_name

                        response_model_properties[field_name] = (
                            formatted_field_properties
                        )

                json_schema_defs = json_schema.get("$defs")
                if json_schema_defs is not None:
                    response_model_properties["$defs"] = {}
                    for def_name, def_properties in json_schema_defs.items():
                        # Handle both regular object definitions and enums
                        if "enum" in def_properties:
                            # This is an enum definition
                            response_model_properties["$defs"][def_name] = {
                                "type": "string",
                                "enum": def_properties["enum"],
                                "description": def_properties.get("description", ""),
                            }
                        else:
                            # This is a regular object definition
                            def_fields = def_properties.get("properties")
                            formatted_def_properties = {}
                            if def_fields is not None:
                                for field_name, field_properties in def_fields.items():
                                    formatted_field_properties = {
                                        prop_name: prop_value
                                        for prop_name, prop_value in field_properties.items()
                                        if prop_name != "title"
                                    }
                                    formatted_def_properties[field_name] = (
                                        formatted_field_properties
                                    )
                            if len(formatted_def_properties) > 0:
                                response_model_properties["$defs"][def_name] = (
                                    formatted_def_properties
                                )

                if len(response_model_properties) > 0:
                    json_output_prompt += "\n<json_fields>"
                    json_output_prompt += f"\n{json.dumps(obj=[key for key in response_model_properties.keys() if key != '$defs'], ensure_ascii=False, indent=2)}"
                    json_output_prompt += "\n</json_fields>"
                    json_output_prompt += "\n\n每个字段的属性说明如下："
                    json_output_prompt += "\n<json_field_properties>"
                    json_output_prompt += f"\n{json.dumps(obj=response_model_properties, ensure_ascii=False, indent=2)}"
                    json_output_prompt += "\n</json_field_properties>"
        else:
            log_warning(f"Could not build json schema for {response_model}")
    else:
        json_output_prompt += "请以JSON格式提供输出"

    json_output_prompt += "\n请以 `{` 开始响应并以 `}` 结束"
    json_output_prompt += "\n你的输出将通过json.loads()转换为Python对象"
    json_output_prompt += "\n请确保输出内容为有效的JSON格式"
    return json_output_prompt
