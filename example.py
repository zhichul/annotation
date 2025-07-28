import dateutil.parser
from annotation import post, main
import dateutil
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

edit0 = post.Post("112718194195663750").latest()
edit1 = post.Post("112718194195663750").latest(cutoff=dateutil.parser.parse("2024-07-02T17:59:29.036Z"))
edit2 = post.Edit.new("112718194195663750", dateutil.parser.parse('2024-07-02T17:59:08.737Z'))
assert edit1 is edit2


print("[RUN1] quality_0_1 --overrides tempterature=0.0")
result = main.annotate("quality_0_1", [edit1], {"quality_0_1": {"temperature": 0.0}})
logger.info(f"[RUN1] Result: {result}")
print("# # # # # # # # # # # # # # # # # # # # # # # # # #")
print("[RUN2] quality_0_2 --overrides tempterature=0.0")
result = main.annotate("quality_0_2", [edit1], {"quality_0_1": {"temperature": 0.0}})
logger.info(f"[RUN2] Result: {result}")

import openai
openai.chat