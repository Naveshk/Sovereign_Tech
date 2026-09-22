def build_context(results: list[dict], max_chars: int = 7000) -> str:
    blocks = []
    used = 0
    for i, item in enumerate(results, 1):
        meta = item.get('metadata') or {}
        source = meta.get('source', 'unknown')
        page = meta.get('page', '?')
        block = f'[Source {i}: {source}, page {page}]\n{item.get("text", "").strip()}'
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return '\n\n'.join(blocks)
