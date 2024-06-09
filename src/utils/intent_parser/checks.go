package main

import (
	"fmt"
	"maps"
	"strconv"
	"strings"
)

// We can assume that all words have been swapped if needed, so we only check for the swapped versions.
func keyphraseCheck(text string, intent Intent) (bool, int, string) {
	var setsPassed int = 0
	var setsNeeded int = 0

	allKeyphraseMatches := make(map[int]string)

	// This is for keyphrases that support substitution
	if intent.AdvancedKeyphrases != nil {
		for _, keyphraseSet := range intent.AdvancedKeyphrases {
			setsNeeded++

			// Take the substitute words (or the original if substitute blank) and create a slice of them
			var keyphrasesToCheck []string
			for keyphrase, newphrase := range keyphraseSet {
				if newphrase != "" {
					keyphrasesToCheck = append(keyphrasesToCheck, newphrase)
				} else {
					keyphrasesToCheck = append(keyphrasesToCheck, keyphrase)
				}

			}

			// Check that slice, save results.
			setKeyphraseMatches := bTextMatches(text, keyphrasesToCheck)
			if len(setKeyphraseMatches) != 0 {
				setsPassed++
				maps.Copy(allKeyphraseMatches, setKeyphraseMatches)
			}
		}
	}

	// This is for regular keyphrases
	if intent.Keyphrases != nil {
		for _, keyphraseSet := range intent.Keyphrases {
			setsNeeded++

			var keyphrasesToCheck []string
			keyphrasesToCheck = append(keyphrasesToCheck, keyphraseSet...)

			// Check that slice, save results.
			setKeyphraseMatches := bTextMatches(text, keyphrasesToCheck)
			if len(setKeyphraseMatches) != 0 {
				setsPassed++
				maps.Copy(allKeyphraseMatches, setKeyphraseMatches)
			}
		}
	}

	if setsPassed == setsNeeded {
		return true, setsPassed, fmt.Sprintf("%s's keyphrase checks passed: %d/%d - \"%v\"", intent.Id, setsPassed, setsNeeded, allKeyphraseMatches)
	} else {
		return false, setsPassed, fmt.Sprintf("%s's keyphrase checks failed: %d/%d - \"%v\"", intent.Id, setsPassed, setsNeeded, allKeyphraseMatches)
	}

}

func prefixCheck(text string, intent Intent) (bool, int, string) {
	for _, prefix := range intent.Prefixes {
		splitPrefix := strings.Split(prefix, " ")
		if len(splitPrefix) == 1 {
			// If the single-word checked prefix is the first word
			if prefix == strings.Split(text, " ")[0] {
				return true, 1, fmt.Sprintf("%s's prefix check passed, \"%v\" found", intent.Id, prefix)
			}
		} else {
			if strings.HasPrefix(text, prefix) {
				return true, 1, fmt.Sprintf("%s's prefix check passed, \"%v\" found", intent.Id, prefix)
			}
		}

	}
	return false, 0, fmt.Sprintf("%s's prefix check failed, none of \"%v\" found", intent.Id, intent.Prefixes)
}

func suffixCheck(text string, intent Intent) (bool, int, string) {
	for _, suffix := range intent.Suffixes {
		splitSuffix := strings.Split(suffix, " ")
		splitText := strings.Split(text, " ")
		if len(splitSuffix) == 1 {
			// If the single-word checked prefix is the first word
			if suffix == splitText[len(splitText)-1] {
				return true, 1, fmt.Sprintf("%s's suffix check passed, \"%v\" found", intent.Id, suffix)
			}
		} else {
			if strings.HasPrefix(text, suffix) {
				return true, 1, fmt.Sprintf("%s's suffix check passed, \"%v\" found", intent.Id, suffix)
			}
		}

	}
	return false, 1, fmt.Sprintf("%s's suffix check passed, none of %v found", intent.Id, intent.Suffixes)
}

func numberCheck(text string, intent Intent) (bool, int, string) {
	for _, word := range strings.Split(text, " ") {
		_, err := strconv.Atoi(word)
		if err == nil {
			return true, 1, fmt.Sprintf("Number check passed: %v found", word)
		}
	}
	return false, 1, "Number check failed: none found"
}
