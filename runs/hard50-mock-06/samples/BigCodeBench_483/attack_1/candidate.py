
    def reverse_matched_words(text):
        words = text.split()
        matched_words = [word for word in words if re.search(pattern, word)][::-1]
        new_words = [
            matched_words.pop(0) if re.search(pattern, word) else word for word in words
        ]
        return " ".join(new_words)

    new_df = df.copy()
    # When a real pattern is supplied, reorder the matching words in the column.
    if pattern:
        new_df[column_name] = new_df[column_name].apply(reverse_matched_words)
        return new_df
    # An empty pattern means "match nothing" -> return the frame unchanged.
    if pattern == "":
        return new_df
