from annotation import api_context_manager, api_context_states
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def annotate(name, edits, cmdline_args=None, no_read=not api_context_states.DEFAULT_READ_CACHE, no_write=not api_context_states.DEFAULT_WRITE_CACHE, only_cache= api_context_states.DEFAULT_ONLY_CACHE, dump_jena=api_context_states.DEFAULT_DUMP_JENA_REQUEST):
    """
    cmdline_args maps names like `evidence_0_0` to a dictionary containing 
    argument overrides (another dict) for that particular annotation.
    Usually such override is specified at the command line but could also be
    by an api call for whatever reason.
    """
    if cmdline_args is None:
        cmdline_args = {}
    logger.info(f"cmdline_args={cmdline_args}")
    with api_context_manager.APIContextManager(cmdline_args=cmdline_args,read_cache=not no_read, write_cache=not no_write, only_cache=only_cache, dump_jena_request=dump_jena):
        f = api_context_states.get_supported_annotation(name)
        logger.info(f"default args: {f.default_args}")
        logger.info(f"override args: {f.cmdline_override_args}")
        result = f(*edits)
    return result

if __name__ == "__main__":
    from annotation import post
    annotate('unary_0_5', [post.Post("112794058427962391").latest()], dump_jena=True, no_read=True)