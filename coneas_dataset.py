import json
import random

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


def load_conan(language, pretraining=False, generation_strategy="zeroshot", fewshot_examples_amount=2,
               fewshot_examples=None):
    fewshot_examples = {} if fewshot_examples is None else fewshot_examples

    j = open("dataset/CONAN/CONAN.json", "r")
    conan = json.load(j)
    if language == "english":
        conan_dataset = [{**dct, **{"language": "EN"}}
                         for dct in filter(lambda cn: cn["cn_id"].startswith("EN"), conan["conan"])]
    elif language == "multi":
        conan_dataset_fr = [{**dct, **{"language": "FR"}}
                            for dct in filter(lambda cn: cn["cn_id"].startswith("FR"), conan["conan"])]
        conan_dataset_it = [{**dct, **{"language": "IT"}}
                            for dct in filter(lambda cn: cn["cn_id"].startswith("IT"), conan["conan"])]
        conan_dataset = conan_dataset_fr + conan_dataset_it

    group_by_tweet = {}
    for cn in conan_dataset:
        if not cn["hateSpeech"] in group_by_tweet:
            group_by_tweet[cn["hateSpeech"]] = [[cn["counterSpeech"]], cn["language"]]
        else:
            group_by_tweet[cn["hateSpeech"]][0].append(cn["counterSpeech"])

    acum = 0
    val_threshold = len(conan_dataset) * 0.8
    if pretraining:
        train_threshold = len(conan_dataset) * 0.7
        train_dataset = []
        val_dataset = []
    test_dataset = []
    keys = list(group_by_tweet.keys())
    keys.sort()
    random.seed(42)
    random.shuffle(keys)
    current_fewshot_examples = {}
    for key in keys:
        if pretraining:
            if acum < train_threshold:
                train_dataset.append({"hateSpeech": key, "counterSpeech": group_by_tweet[key][0],
                                      "language": group_by_tweet[key][1]})
            elif acum < val_threshold:
                val_dataset.append({"hateSpeech": key, "counterSpeech": group_by_tweet[key][0],
                                    "language": group_by_tweet[key][1]})
        elif generation_strategy == "fewshot":
            language = group_by_tweet[key][1]
            if language not in current_fewshot_examples:
                current_fewshot_examples[language] = 1
                fewshot_examples[language] = [{"hateSpeech": key, "counterSpeech": group_by_tweet[key][0][0]}]
            elif current_fewshot_examples[language] < fewshot_examples_amount:
                current_fewshot_examples[language] += 1
                fewshot_examples[language].append({"hateSpeech": key, "counterSpeech": group_by_tweet[key][0][0]})
        if acum >= val_threshold:
            test_dataset.append({"hateSpeech": key, "counterSpeech": group_by_tweet[key][0],
                                 "language": group_by_tweet[key][1]})

        acum += len(group_by_tweet[key][0])
    if pretraining:
        return [test_dataset, train_dataset, val_dataset]
    return [test_dataset]


def load_asohmo(language, use_extra_info="", pretraining=False, generation_strategy="zeroshot",
                fewshot_examples_amount=2, fewshot_examples=None):
    fewshot_examples = {} if fewshot_examples is None else fewshot_examples

    lang_setting = language.replace("multi", "spanish")
    # if language == "english":
    cns_by_tweet, nonargs, cn_length, cn_type_not_present = parse_dataset(
        f"dataset/ASOHMO/{lang_setting}/test/*.conll", use_extra_info=use_extra_info, language=language)
    if pretraining:
        cns_by_tweet_train, nonargs2, cn_length2, cn_type_not_present2 = parse_dataset(
            f"dataset/ASOHMO/{lang_setting}/train/*.conll", use_extra_info=use_extra_info, language=language)
        cns_by_tweet_dev, nonargs3, cn_length3, cn_type_not_present3 = parse_dataset(
            f"dataset/ASOHMO/{lang_setting}/dev/*.conll", use_extra_info=use_extra_info, language=language)
        print(f"{nonargs} - {nonargs2} - {nonargs3}")
        nonargs += nonargs2 + nonargs3
        cn_length += cn_length2 + cn_length3
        cn_type_not_present += cn_type_not_present2 + cn_type_not_present3
        if language == "multi":
            cns_by_tweet_en, nonargs_en, cn_length_en, cn_type_not_present_en = parse_dataset(
                f"dataset/ASOHMO/english/test/*.conll", use_extra_info=use_extra_info, language=language)
            cns_by_tweet_train2_en, nonargs2_en, cn_length2_en, cn_type_not_present2_en = parse_dataset(
                f"dataset/ASOHMO/english/train/*.conll", use_extra_info=use_extra_info, language=language)
            cns_by_tweet_dev3_en, nonargs3_en, cn_length3_en, cn_type_not_present3_en = parse_dataset(
                f"dataset/ASOHMO/english/dev/*.conll", use_extra_info=use_extra_info, language=language)

            cns_by_tweet = {**cns_by_tweet, **cns_by_tweet_en}
            cns_by_tweet_train = {**cns_by_tweet_train, **cns_by_tweet_train2_en}
            cns_by_tweet_dev = {**cns_by_tweet_dev, **cns_by_tweet_dev3_en}

            nonargs += nonargs_en + nonargs2_en + nonargs3_en
            cn_length += cn_length_en + cn_length2_en + cn_length3_en
            cn_type_not_present += cn_type_not_present_en + cn_type_not_present2_en + cn_type_not_present3_en
    print(f"Counter narratives without the required type of counter-narrative: {cn_type_not_present}")
    print(f"Non arg examples discarted for not having CN: {nonargs}")
    if pretraining:
        print(f"{len(cns_by_tweet.keys())} - {len(cns_by_tweet_train.keys())} - {len(cns_by_tweet_dev.keys())}")
    test_dataset = []
    if pretraining:
        train_dataset = []
        val_dataset = []

    keys = list(cns_by_tweet.keys())
    keys.sort()
    random.seed(42)
    random.shuffle(keys)
    current_fewshot_examples = {}
    for key in keys:
        if pretraining:
            for cn in cns_by_tweet[key]["cns"]:
                to_append = {"hateSpeech": key + cns_by_tweet[key]["extra_info"], "counterSpeech": cn,
                             "language": cns_by_tweet[key]["lang"]}
                test_dataset.append(to_append)
        else:
            to_append = {"hateSpeech": key + cns_by_tweet[key]["extra_info"], "counterSpeech": cns_by_tweet[key]["cns"],
                         "language": cns_by_tweet[key]["lang"]}
            language_code = "ES" if language == "multi" else "EN"
            if (generation_strategy == "fewshot" and
                (language_code not in current_fewshot_examples or
                 current_fewshot_examples[language_code] < fewshot_examples_amount)):
                if language_code not in current_fewshot_examples:
                    current_fewshot_examples[language_code] = 1
                    fewshot_examples[language_code] = [{"hateSpeech": key, "counterSpeech": cns_by_tweet[key]["cns"][0]}]
                else:
                    current_fewshot_examples[language_code] += 1
                    fewshot_examples[language_code].append({"hateSpeech": key, "counterSpeech": cns_by_tweet[key]["cns"][0]})
            else:
                test_dataset.append(to_append)

    if pretraining:
        for key in cns_by_tweet_train:
            for cn in cns_by_tweet_train[key]["cns"]:
                to_append = {"hateSpeech": key + cns_by_tweet_train[key]["extra_info"], "counterSpeech": cn,
                             "language": cns_by_tweet_train[key]["lang"]}
                train_dataset.append(to_append)
        for key in cns_by_tweet_dev:
            for cn in cns_by_tweet_dev[key]["cns"]:
                to_append = {"hateSpeech": key + cns_by_tweet_dev[key]["extra_info"], "counterSpeech": cn,
                             "language": cns_by_tweet_dev[key]["lang"]}
                val_dataset.append(to_append)

    if pretraining:
        return [test_dataset, train_dataset, val_dataset]
    return [test_dataset]
