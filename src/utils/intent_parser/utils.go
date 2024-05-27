package main

import "strings"

// The point of this function is to make it much faster to replace things in a more relevant way,
// with whole-word matches for single-word checks, and regular replaces for multi-word strings.
func bReplace(text string, oldText string, newText string) string {
	if newText != "" {
		// If the keyphrase is a single word, we look for whole word matches ("go" won't match within "golf")
		// If multiple words, we just replace all instances of oldText with newText
		if len(strings.Split(oldText, " ")) == 1 {

			textWords := strings.Split(text, " ")
			for index, word := range textWords {
				if word == oldText {
					textWords[index] = newText
				}
			}
			text = strings.Join(textWords, " ")
		} else {
			text = strings.Replace(text, oldText, newText, -1)
		}
	}
	return text
}
