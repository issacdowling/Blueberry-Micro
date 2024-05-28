package main

import (
	"fmt"
	"maps"
	"strings"
)

func keyphraseCheck(text string, intent Intent) (bool, string) {
	var setsPassed int = 0
	var setsNeeded int = 0
	// For all keyphrases, replace with their substitute values if not empty
	allKeyphraseMatches := make(map[int]string)
	for _, keyphraseSet := range intent.Keyphrases {
		setsNeeded++

		for keyphrase := range keyphraseSet {
			setKeyphraseMatches := bTextMatches(text, []string{keyphrase})
			if len(setKeyphraseMatches) != 0 {
				setsPassed++
				maps.Copy(allKeyphraseMatches, setKeyphraseMatches)
			}
		}
	}

	if setsPassed == setsNeeded {
		return true, fmt.Sprintf("%s's keyphrase checks passed: %d/%d - %v", intent.Id, setsPassed, setsNeeded, allKeyphraseMatches)
	} else {
		return false, fmt.Sprintf("%s's keyphrase checks failed: %d/%d - %v", intent.Id, setsPassed, setsNeeded, allKeyphraseMatches)
	}

}

func prefixCheck(text string, intent Intent) (bool, string) {
	for _, prefix := range intent.Prefixes {
		splitPrefix := strings.Split(prefix, " ")
		if len(splitPrefix) == 1 {
			// If the single-word checked prefix is the first word
			if prefix == strings.Split(text, " ")[0] {
				return true, fmt.Sprintf("Prefix %v found", prefix)
			}
		} else {
			if strings.HasPrefix(text, prefix) {
				return true, fmt.Sprintf("Prefix %v found", prefix)
			}
		}

	}
	return false, fmt.Sprintf("Prefix not found from %v", intent.Prefixes)
}

func suffixCheck(text string, intent Intent) (bool, string) {
	for _, suffix := range intent.Suffixes {
		splitSuffix := strings.Split(suffix, " ")
		splitText := strings.Split(text, " ")
		if len(splitSuffix) == 1 {
			// If the single-word checked prefix is the first word
			if suffix == splitText[len(splitText)-1] {
				return true, fmt.Sprintf("Suffix %v found", suffix)
			}
		} else {
			if strings.HasPrefix(text, suffix) {
				return true, fmt.Sprintf("Suffix %v found", suffix)
			}
		}

	}
	return false, fmt.Sprintf("Suffix not found from %v", intent.Suffixes)
}

func collectionCheck(text string, intent Intent) (bool, string) {
	return false, ""
}
