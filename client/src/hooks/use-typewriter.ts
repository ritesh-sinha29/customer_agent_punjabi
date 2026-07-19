import { useEffect, useState } from "react";

export function useTypewriter(
  words: string[],
  typingSpeed = 30,      // Fast typing speed (ms per char)
  deletingSpeed = 15,     // Fast deleting speed (ms per char)
  delayBetweenWords = 2000 // How long to show the full suggestion
) {
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const [currentText, setCurrentText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    setCurrentWordIndex(0);
    setCurrentText("");
    setIsDeleting(false);
  }, [words]);

  useEffect(() => {
    if (words.length === 0) return;

    let timer: NodeJS.Timeout;
    const currentWord = words[currentWordIndex];

    if (isDeleting) {
      timer = setTimeout(() => {
        setCurrentText((prev) => prev.slice(0, -1));
      }, deletingSpeed);
    } else {
      timer = setTimeout(() => {
        setCurrentText((prev) => currentWord.slice(0, prev.length + 1));
      }, typingSpeed);
    }

    // Pause once word is fully typed
    if (!isDeleting && currentText === currentWord) {
      clearTimeout(timer);
      timer = setTimeout(() => {
        setIsDeleting(true);
      }, delayBetweenWords);
    }

    // Move to next word once fully deleted
    if (isDeleting && currentText === "") {
      setIsDeleting(false);
      setCurrentWordIndex((prev) => (prev + 1) % words.length);
    }

    return () => clearTimeout(timer);
  }, [currentText, isDeleting, currentWordIndex, words, typingSpeed, deletingSpeed, delayBetweenWords]);

  return currentText;
}
