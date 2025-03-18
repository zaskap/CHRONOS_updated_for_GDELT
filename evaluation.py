# from: https://github.com/complementizer/news-tls

from pathlib import Path
from tilse.data.timelines import Timeline as TilseTimeline
from tilse.data.timelines import GroundTruth as TilseGroundTruth
from tilse.evaluation import rouge
from pprint import pprint


def get_scores(metric_desc, pred_tl, groundtruth, evaluator):

    if metric_desc == "concat":
        return {"concat": evaluator.evaluate_concat(pred_tl, groundtruth)}
    elif metric_desc == "agreement":
        return {"agreement": evaluator.evaluate_agreement(pred_tl, groundtruth)}
    elif metric_desc == "align_date_costs":
        return {"align_date_costs": evaluator.evaluate_align_date_costs(pred_tl, groundtruth)}
    elif metric_desc == "align_date_content_costs":
        return {"align_date_content_costs": evaluator.evaluate_align_date_content_costs(
            pred_tl, groundtruth)}
    elif metric_desc == "align_date_content_costs_many_to_one":
        return {"align_date_content_costs_many_to_one": evaluator.evaluate_align_date_content_costs_many_to_one(
            pred_tl, groundtruth)}
    else:
        return evaluator.evaluate_all(pred_tl, groundtruth)


def zero_scores():
    return {'f_score': 0., 'precision': 0., 'recall': 0.}


def evaluate_dates(pred, ground_truth):
    pred_dates = pred.get_dates()
    ref_dates = ground_truth.get_dates()
    shared = pred_dates.intersection(ref_dates)
    n_shared = len(shared)
    n_pred = len(pred_dates)
    n_ref = len(ref_dates)
    prec = n_shared / n_pred
    rec = n_shared / n_ref
    if prec + rec == 0:
        f_score = 0
    else:
        f_score = 2 * prec * rec / (prec + rec)
    return {
        'precision': prec,
        'recall': rec,
        'f_score': f_score,
    }


def get_average_results(tmp_results):
    # rouge_1 = zero_scores()
    # rouge_2 = zero_scores()
    date_prf = zero_scores()
    rouge_scores = {'concat': {'rouge_1': zero_scores(), 'rouge_2': zero_scores()},
                    'agreement': {'rouge_1': zero_scores(), 'rouge_2': zero_scores()},
                    'align_date_costs': {'rouge_1': zero_scores(), 'rouge_2': zero_scores()},
                    'align_date_content_costs': {'rouge_1': zero_scores(), 'rouge_2': zero_scores()},
                    'align_date_content_costs_many_to_one': {'rouge_1': zero_scores(), 'rouge_2': zero_scores()},
                    }
    for rouge_res, date_res, _ in tmp_results:
        metrics = [m for m in date_res.keys() if m != 'f_score']
        for m in metrics:
            for evaluator in rouge_res.keys():
                rouge_scores[evaluator]['rouge_1'][m] += rouge_res[evaluator]['rouge_1'][m]
                rouge_scores[evaluator]['rouge_2'][m] += rouge_res[evaluator]['rouge_2'][m]
            date_prf[m] += date_res[m]
    
    n = len(tmp_results)
    for evaluator in rouge_scores.keys():
        for metric in ['rouge_1', 'rouge_2']:
            for k in ['precision', 'recall']:
                rouge_scores[evaluator][metric][k] /= n
            prec = rouge_scores[evaluator][metric]['precision']
            rec = rouge_scores[evaluator][metric]['recall']
            if prec + rec == 0:
                rouge_scores[evaluator][metric]['f_score'] = 0.
            else:
                rouge_scores[evaluator][metric]['f_score'] = (2 * prec * rec) / (prec + rec)

    for k in ['precision', 'recall']:
        date_prf[k] /= n
    prec = date_prf['precision']
    rec = date_prf['recall']
    if prec + rec == 0:
        date_prf['f_score'] = 0.
    else:
        date_prf['f_score'] = (2 * prec * rec) / (prec + rec)

    return rouge_scores, {"date_score": date_prf}