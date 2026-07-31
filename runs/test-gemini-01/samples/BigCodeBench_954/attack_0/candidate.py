import random
import re


def task_func(target_words, n_sentences, vocabulary):
    """
    Generate sentences with spaces in certain target words replaced by underscores.
    """
    if n_sentences < 0:
        raise ValueError("n_sentences cannot be negative.")
    if not vocabulary:
        raise ValueError("Vocabulary cannot be empty.")

    # Apply the longest target phrases first so that longer multi-word matches
    # take precedence over any shorter phrases they may contain.
    ordered_targets = sorted(target_words, key=len, reverse=True)

    sentences = []
    for _ in range(n_sentences):
        sentence = " ".join(random.choices(vocabulary, k=10))
        for word in ordered_targets:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            sentence = pattern.sub(word.replace(" ", "_"), sentence)
        sentences.append(sentence.lower())
    return sentences
