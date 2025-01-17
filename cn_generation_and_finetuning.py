import argparse
import evaluate
import numpy as np
import pandas as pd
import torch

from datasets import Dataset
from sentence_transformers import SentenceTransformer, util
from transformers import (AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM, DataCollatorForSeq2Seq,
                          Seq2SeqTrainer, Seq2SeqTrainingArguments)

from coneas_dataset import load_conan, load_asohmo

device = torch.device("cuda")
parser = argparse.ArgumentParser(
    description="Train models for identifying argumentative components inside the ASFOCONG dataset")
parser.add_argument("dataset", type=str, choices=["conan", "asohmo", "both"])
parser.add_argument("generation_strategy", type=str, choices=["zeroshot", "fewshot", "finetuned", "pretraining"])
parser.add_argument("language", type=str, choices=["english", "multi"])
parser.add_argument("--use_extra_info", type=str, choices=["collective", "premises", "all", ""], default="")
parser.add_argument("--cn_strategy", type=str, default="", choices=["a", "b", "c", ""])
parser.add_argument("--model_name", type=str, default="google/flan-t5-base")

args = parser.parse_args()

model_name = args.model_name
language = args.language
pretraining = args.generation_strategy == "pretraining" or args.generation_strategy == "adapt_to_strategy"

FEWSHOT_EXAMPLES_AMOUNT = 2
fewshot_examples = {}


if args.dataset == "conan":
    print("Loading conan dataset")
    datasetss = load_conan(args.language, pretraining=pretraining, generation_strategy=args.generation_strategy,
                           fewshot_examples_amount=FEWSHOT_EXAMPLES_AMOUNT, fewshot_examples=fewshot_examples)
elif args.dataset == "asohmo":
    print("Loading asohmo dataset")
    exxtra_info = args.use_extra_info
    if args.cn_strategy == "a":
        if args.use_extra_info == "premises":
            exxtra_info = "cn_a"
        else:
            exxtra_info = "cn_a_no_info"
    elif args.cn_strategy == "b":
        if args.use_extra_info == "collective":
            exxtra_info = "cn_b"
        else:
            exxtra_info = "cn_b_no_info"
    elif args.cn_strategy == "c":
        if args.use_extra_info == "premises":
            exxtra_info = "cn_c"
        else:
            exxtra_info = "cn_c_no_info"
    datasetss = load_asohmo(args.language, use_extra_info=exxtra_info, pretraining=pretraining,
                            generation_strategy=args.generation_strategy,
                            fewshot_examples_amount=FEWSHOT_EXAMPLES_AMOUNT, fewshot_examples=fewshot_examples)
else:
    print("Loading both datasets")
    datasetss1 = load_asohmo(args.language, pretraining=pretraining, generation_strategy=args.generation_strategy,
                             fewshot_examples_amount=FEWSHOT_EXAMPLES_AMOUNT, fewshot_examples=fewshot_examples)
    datasetss2 = load_conan(args.language, pretraining=pretraining, generation_strategy=args.generation_strategy,
                            fewshot_examples_amount=FEWSHOT_EXAMPLES_AMOUNT, fewshot_examples=fewshot_examples)
    datasetss = [dtst1 + dtst2 for dtst1, dtst2 in zip(datasetss1, datasetss2)]

test_dataset = datasetss[0]
if pretraining:
    train_dataset = datasetss[1]
    val_dataset = datasetss[2]

test_data = Dataset.from_pandas(pd.DataFrame(test_dataset))
if pretraining:
    train_data = Dataset.from_pandas(pd.DataFrame(train_dataset))
    val_data = Dataset.from_pandas(pd.DataFrame(val_dataset))


tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.add_special_tokens({'pad_token': '[PAD]'})
# tokenizer.pad_token = tokenizer.eos_token

# print("llllllllllllllllllllllllllllllllllllllllllll")
# print(tokenizer.pad_token)
# print(tokenizer.eos_token)

new_tokens = ["<SHS>", "<EHS>", "<SCN>", "<ECN>"]
num_new_tokens = tokenizer.add_tokens(new_tokens)
print("ECN token: ")
tkn = tokenizer("<ECN>")
print(tkn)
eos_token_id = tkn["input_ids"][0]

print("We added ", num_new_tokens, " new tokens")

if args.generation_strategy == "finetuned":
    # if args.cn_strategy != "":
    model_name = f"pretrained_models/{args.dataset}_{args.model_name.replace('/', '-')}_multi_{args.use_extra_info}_{args.cn_strategy}_2e-05_8Epochs"
    # else:
    #     model_name = f"pretrained_models/{args.dataset}_{args.model_name.replace('/', '-')}_multi_{args.use_extra_info}_2e-05_8Epochs"

if model_name.startswith("bigscience") or model_name.startswith("aleksickx/llama-7b-hf") or model_name.startswith("EleutherAI/gpt-j-6b"):
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.to(device)
else:
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to(device)

model.resize_token_embeddings(len(tokenizer))

def generate_prompt(text, strategy, language):
    initial_prompt = "Generate a non-hateful response for the following hate messages:\n"
    if language == "ES":
        initial_prompt = "Genera una respuesta sin odio a los siguientes mensajes de odio:\n"
    elif language == "FR":
        initial_prompt = "Générez une réponse pour les messages haineux suivants:\n"
    elif language == "IT":
        initial_prompt = "Genera una risposta per i seguenti messaggi di odio:\n"

    if strategy == "zeroshot":
        return  initial_prompt + text + " => "
    elif strategy == "fewshot":
        example_list = []
        for examp in fewshot_examples[language]:
            example_list.append("<SHS>" + examp["hateSpeech"] + "<EHS> => <SCN>" + examp["counterSpeech"] + "<ECN>")
        examples = '\n'.join(example_list)
        # examples = """
        #     I hate Muslims. They should not exist. => Muslims are human too. People can choose their own religion.
        #     All immigrants are criminals and should be deported. => Most immigrants are hard-working people trying to have a better life for them and their families.
        #     Immigrants are lazy and cost a lot of money to the taxpayers. => Immigrants usually have the worst jobs and pay taxes as everyone else.
        # """
        # if language == "ES":
            # examples = """
            #     Odio a los musulmanes. No deberían existir. => Los musulmanes también son seres humanos. Las personas pueden elegir su propia religión.
            #     Todos los inmigrantes son criminales y deberían ser deportados. => La mayoría de los inmigrantes son gente trabajadora tratando de tener una vida mejor para ellos y sus familias.
            #     Los inmigrantes son vagos y cuestan mucho dinero a los contribuyentes. => Los inmigrantes usualmente tienen los peores trabajos y pagan impuestos como cualquier otro.
            # """
        # if language == "FR":
            # examples = """
            #     Je déteste les musulmans. Ils ne devraient pas exister. => Les musulmans sont humains aussi. Les gens peuvent choisir leur propre religion.
            #     Tous les immigrés sont des criminels et doivent être expulsés. => La plupart des immigrants sont des travailleurs qui essaient d'améliorer leur vie et celle de leur famille.
            #     Les immigrants sont paresseux et coûtent très cher aux contribuables. => Les immigrés ont généralement les pires emplois et paient des impôts comme tout le monde.
            # """
        # if language == "IT":
            # examples = """
            #     Odio i musulmani. Non dovrebbero esistere. => Anche i musulmani sono umani. Le persone possono scegliere la propria religione.
            #     Tutti gli immigrati sono criminali e dovrebbero essere espulsi. => La maggior parte degli immigrati sono persone laboriose che cercano di avere una vita migliore per loro e per le loro famiglie.
            #     Gli immigrati sono pigri e costano un sacco di soldi ai contribuenti. => Gli immigrati di solito hanno i lavori peggiori e pagano le tasse come tutti gli altri.
            # """

        # print("==============================================")
        return initial_prompt + examples + '\n' + text + " => "
    elif strategy == "finetuned" or strategy == "pretraining":
        return initial_prompt + "<SHS>" + text + "<EHS> => "

datasett = test_dataset
if pretraining:
    datasett += train_dataset
    datasett += val_dataset

print(len(test_dataset))
dataset_tokenized = list(map(lambda sample: tokenizer(generate_prompt(sample["hateSpeech"], args.generation_strategy, sample["language"]), truncation=True)["input_ids"], datasett))
max_source_length = max([len(x) for x in dataset_tokenized])

if pretraining:
    target_tokenized = list(map(lambda sample: tokenizer("<SCN>" + sample["counterSpeech"] + "<ECN>", truncation=True)["input_ids"], datasett))
    max_target_length = max([len(x) for x in target_tokenized])


def preprocess(sample, padding="max_length"):
    inputs = generate_prompt(sample["hateSpeech"], args.generation_strategy, sample["language"])
    if pretraining:
        model_inputs = tokenizer(inputs, padding=padding, max_length=max_source_length, truncation=True)
    else:
        model_inputs = tokenizer(inputs, padding=padding, max_length=max_source_length, truncation=True, return_tensors="pt")
        model_inputs = model_inputs.to(device)
    if pretraining:
        # model_inputs["input_ids"] = torch.flatten(model_inputs["input_ids"])
        # model_inputs["attention_mask"] = torch.flatten(model_inputs["attention_mask"])
        labels = tokenizer("<SCN> " + sample["counterSpeech"] + " <ECN>", padding=padding, max_length=max_target_length, truncation=True)
        if padding == "max_length":
            labels["input_ids"] = [
                (l if l != tokenizer.pad_token_id else -100) for l in labels["input_ids"]
            ]
        model_inputs["labels"] = labels["input_ids"]
    else:
        model_inputs["labels"] = sample["counterSpeech"]
    return model_inputs

sbert = SentenceTransformer('all-MiniLM-L6-v2')

# Metric
metric1 = evaluate.load("bertscore")
metric2 = evaluate.load("bleu")
metric3 = evaluate.load("rouge")


def evaluate_generation(testing_datasets, top_sampling=False, beam_search=False, temperature=False):

    f1_avg = 0.0
    bleu_avg = 0.0
    rouge_avg = 0.0
    sbert_avg = 0.0

    filename = f"{args.dataset}_{args.model_name}_{args.language}_2e-05_{args.generation_strategy}_{args.use_extra_info}_{args.cn_strategy}_{top_sampling}_{beam_search}_{temperature}".replace("/", "-")
    w = open(filename, 'w')
    for example in testing_datasets:
        inputt = example[0]
        tweet = example[1]
        # inputt.to(device)
        if beam_search:
            result = model.generate(**inputt, max_new_tokens=150, no_repeat_ngram_size=4, num_beams=4, early_stopping=True)#, eos_token_id = eos_token_id)
        elif top_sampling:
            result = model.generate(**inputt, max_new_tokens=512, no_repeat_ngram_size=4, do_sample=True, top_k=0, top_p=0.92, eos_token_id = eos_token_id)
        elif temperature:
            result = model.generate(**inputt, max_new_tokens=512, no_repeat_ngram_size=4, do_sample=True, temperature=0.7, eos_token_id = eos_token_id)
        else:
            result = model.generate(**inputt, max_new_tokens=512, no_repeat_ngram_size=4, eos_token_id = eos_token_id)
        preds = str(tokenizer.batch_decode(result)[0])
        print("----------------------------------tweet-----------------------------")
        print(tweet)
        print("----------------------------------preds-----------------------------")
        print(preds)
        print("\n")
        for labels in inputt["labels"]:

            result1 = metric1.compute(predictions=[preds], references=[labels], lang="en")
            result2 = metric2.compute(predictions=[preds], references=[labels])
            result3 = metric3.compute(predictions=[preds], references=[labels])

            cosine_scores_preds = sbert.encode([preds], convert_to_tensor=True)
            cosine_scores_labels = sbert.encode([labels], convert_to_tensor=True)

            sbert_score = util.cos_sim(cosine_scores_preds, cosine_scores_labels)

            f1_avg += result1["f1"][0]
            bleu_avg += result2["bleu"]
            rouge_avg += result3["rougeL"]
            sbert_avg += sbert_score[0][0].item()

            w.write("---------------------------------------------------------\n")
            w.write(tweet)
            w.write('\n')
            w.write(labels)
            w.write("\n")
            w.write(preds)
            w.write("\n")
            w.write(str(result1))
            w.write("\n")
            w.write(str(result2))
            w.write("\n")
            w.write(str(result3))
            w.write("\n")
            w.write(str(sbert_score[0][0].item()))
            w.write("\n")

    w.write("========================================\n")
    w.write("F1 AVG:\n")
    w.write(str(f1_avg / len(testing_datasets)))
    w.write("\n")
    w.write("Bleu AVG:\n")
    w.write(str(bleu_avg / len(testing_datasets)))
    w.write("\n")
    w.write("Rouge AVG:\n")
    w.write(str(rouge_avg / len(testing_datasets)))
    w.write("\n")
    w.write("SBERT AVG:\n")
    w.write(str(sbert_avg / len(testing_datasets)))
    w.close()


if pretraining:

    train_data = train_data.map(preprocess)
    val_data = val_data.map(preprocess)
    test_data = test_data.map(preprocess)

    def compute_metrics(eval_preds):
        preds, labels = eval_preds
        if isinstance(preds, tuple):
            preds = preds[0]
        print(labels)
        print("=============================")
        print(preds)
        decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
        # Replace -100 in the labels as we can't decode them.
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
        # decoded_inputs = tokenizer.batch_decode(inputs, skip_special_tokens=True)

        # Some simple post-processing
        # decoded_preds, decoded_labels, decoded_inputs = postprocess_text(decoded_preds, decoded_labels, decoded_inputs)

        # Using rouge score
        result = metric3.compute(predictions=decoded_preds, references=decoded_labels)


        # result = {k: round(v * 100, 4) for k, v in result.items()}
        prediction_lens = [np.count_nonzero(pred != tokenizer.pad_token_id) for pred in preds]
        result["gen_len"] = np.mean(prediction_lens)
        result["prediction"] = decoded_preds
        result["labels"] = decoded_labels
        # result["inputs"] = decoded_inputs
        return result

    # we want to ignore tokenizer pad token in the loss
    label_pad_token_id = -100
    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        label_pad_token_id=label_pad_token_id,
        # pad_to_multiple_of=8
    )

    # print(train_data[0])

    # Hugging Face repository id
    repository_id = f"{model_name.split('/')[1]}-english"

    # Define training args
    training_args = Seq2SeqTrainingArguments(
        output_dir=repository_id,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=8,
        predict_with_generate=True,
        generation_max_length=200,
        generation_num_beams=4,
        # TODO: turn this on and check if it works
        fp16=False, # Overflows with fp16
        learning_rate=2e-04,
        num_train_epochs=8,
        # include_inputs_for_metrics=True,
        # logging & evaluation strategies
        # logging_dir=f"{repository_id}/logs",
        # logging_strategy="steps",
        logging_steps=5,
        # evaluation_strategy="epoch",
        # save_strategy="epoch",
        # save_total_limit=10,
        # load_best_model_at_end=True,
        # metric_for_best_model="overall_f1",
        # push to hub parameters
        # report_to="tensorboard",
        # push_to_hub=False,
        # hub_strategy="every_save",
        # hub_model_id=repository_id,
        # hub_token=HfFolder.get_token(),
    )

    # Create Trainer instance
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=train_data,
        eval_dataset=val_data,
        compute_metrics=compute_metrics,
    )


    trainer.train()

    trainer.save_model(f"{args.dataset}_{args.model_name}_{args.language}_{args.use_extra_info}_{args.cn_strategy}_2e-05_8Epochs".replace("/", "-"))
else:
    preprocessed_dataset = []
    for example in test_data:
        preprocessed_dataset.append([preprocess(example), example["hateSpeech"]])

    print("generating")
    # evaluate_generation(preprocessed_dataset)
    # evaluate_generation(preprocessed_dataset, top_sampling=True)
    # evaluate_generation(preprocessed_dataset, temperature=True)
    evaluate_generation(preprocessed_dataset, beam_search=True)
