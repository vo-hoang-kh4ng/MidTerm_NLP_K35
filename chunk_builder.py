class ChunkBuilder:
    
    def build(self, sentences, chunk_size=5):
        """
        Build chunk cho LLM.
        """
        chunks = []

        for i in range(0, len(sentences), chunk_size):
            group = sentences[i:i + chunk_size]

            llm_lines = []
            search_lines = []

            for item in group:
                sentence = item["sentence"].strip()
                
                # Để marker và câu trên cùng 1 dòng rõ ràng
                marker = f"[[[{item['sentence_id']}]]] {sentence}"

                llm_lines.append(marker)
                search_lines.append(sentence)

            chunks.append({
                "items": group,
                "text": "\n".join(llm_lines),
                "search_text": "\n".join(search_lines)
            })

        return chunks