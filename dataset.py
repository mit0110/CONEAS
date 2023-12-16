from glob import glob


def parse_dataset(filenames, use_extra_info="", language="english"):
    cns_by_tweet = {}
    nonargs = 0
    cn_length = 0
    cn_type_not_present = 0
    print("Reading files", filenames)
    for filename in glob(filenames):
        f = open(filename, "r")
        tweet_list = []
        is_arg = True
        need_collective = use_extra_info == "collective" or use_extra_info == "all" or use_extra_info == "cn_b"
        need_premises = use_extra_info == "premises" or use_extra_info == "all" or use_extra_info == "cn_a"
        need_justification = use_extra_info == "cn_c"
        if need_collective:
            collective = []
            consecutive_collective = False
            property = []
            consecutive_property = False
        if need_premises or need_justification:
            justification = []
            consecutive_just = False
            if need_premises:
                conclusion = []
                consecutive_conc = False
                pivot = []
                consecutive_pivot = False
        prev_line = ["", "", "", "", "", "", "", "", ""]
        for line in f:
            splitted_line = line.split("\t")
            if splitted_line[1].startswith("NoArgumentative"):
                is_arg = False
                break
            if splitted_line[4].startswith("Collective") and need_collective:
                if not prev_line[4].startswith("Collective") and consecutive_collective:
                    collective.append(" - ")
                collective.append(splitted_line[0])
                consecutive_collective = True
            if splitted_line[5].startswith("Property") and need_collective:
                if not prev_line[5].startswith("Property") and consecutive_property:
                    property.append(" - ")
                property.append(splitted_line[0])
                consecutive_property = True
            if splitted_line[2].startswith("Premise2Justification") and (need_premises or need_justification):
                if not prev_line[2].startswith("Premise2Justification") and consecutive_just:
                    justification.append(" - ")
                justification.append(splitted_line[0])
                consecutive_just = True
            if splitted_line[3].startswith("Premise1Conclusion") and need_premises:
                if not prev_line[3].startswith("Premise1Conclusion") and consecutive_conc:
                    conclusion.append(" - ")
                conclusion.append(splitted_line[0])
                consecutive_conc = True
            if splitted_line[6].startswith("pivot") and need_premises:
                if not prev_line[6].startswith("pivot") and consecutive_pivot:
                    pivot.append(" - ")
                pivot.append(splitted_line[0])
                consecutive_pivot = True
            if (not splitted_line[7].startswith("O")) and need_premises or need_justification:
                type_just = splitted_line[7].strip()
            if (not splitted_line[8].startswith("O")) and need_premises:
                type_conc = splitted_line[8].strip()

            tweet_list.append(splitted_line[0])
            prev_line = splitted_line
            # if splitted_line[]
        if not is_arg:
            nonargs += 1
            continue
        tweet = " ".join(tweet_list)
        extra_info = ""
        if need_collective:
            if language == "english":
                extra_info += " | Collective: " + " ".join(collective) + " | Property: " + " ".join(property)
            else:
                extra_info += " | Colectivo: " + " ".join(collective) + " | Propiedad: " + " ".join(property)
        if need_premises:
            if language == "english":
                extra_info += (" | Justification: " + " ".join(justification) + " (" + type_just + ") " +
                               " | Conclusion: " + " ".join(conclusion) + " (" + type_conc + ") " + " | Pivot: " + 
                               " ".join(pivot))
            else:
                extra_info += (" | Justificación: " + " ".join(justification) + " (" + type_just + ") " + 
                               " | Conclusión: " + " ".join(conclusion) +  " (" + type_conc + ") " + " | Pivot: " + 
                               " ".join(pivot))
        elif need_justification:
            if language == "english":
                extra_info = " | Justification: " + " ".join(justification) + " (" + type_just + ") "
            else:
                extra_info = " | Justificación: " + " ".join(justification) + " (" + type_just + ") "

        counternarratives = []
        cn = open(filename.replace("conll", "cn"), "r")
        if use_extra_info.startswith("cn_"):
            cn_not_present = False
        for idx, line in enumerate(cn):
            if use_extra_info == "cn_a" or use_extra_info == "cn_a_no_info":
                if idx == 0:
                    if line.replace("\n", "").strip() != "":
                        counternarratives.append(line)
                    else:
                        cn_not_present = True
            elif use_extra_info == "cn_b" or use_extra_info == "cn_b_no_info":
                if idx == 1:
                    if line.replace("\n", "").strip() != "":
                        counternarratives.append(line)
                    else:
                        cn_not_present = True
            elif use_extra_info == "cn_c" or use_extra_info == "cn_c_no_info":
                if idx == 2:
                    if line.replace("\n", "").strip() != "":
                        counternarratives.append(line)
                    else:
                        cn_not_present = True
            else:
                if line.replace("\n", "").strip() != "":
                    counternarratives.append(line)
        if tweet in cns_by_tweet:
            cns_by_tweet[tweet]["cns"] += counternarratives
        else:
            if use_extra_info.startswith("cn_") and cn_not_present:
                cn_type_not_present += 1
            else:
                cns_by_tweet[tweet] = {
                    "cns": counternarratives, "lang": "EN" 
                    if language == "english" else "ES", "extra_info": extra_info}
        cn_length += len(counternarratives)
        if use_extra_info.startswith("cn_") and len(counternarratives) > 1:
            print("Error, unexpected number of counternarratives", len(counternarratives))
    return cns_by_tweet, nonargs, cn_length, cn_type_not_present
