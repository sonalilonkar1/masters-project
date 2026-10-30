# Report References

**Status:** the literature review is being rewritten; the Workbook 2 version was shared for reference only. **Rule:** the report cites only papers the team has read and included in its literature review. Draft chapters use author-year keys, for example [Cortez 2017], because the Workbook 2 literature review and `docs/references/References.md` number the references differently. Keys are converted to IEEE numbers, in order of first citation, when the full report is assembled.

---

## A. Papers from the earlier literature review (Workbook 2 / `References.md`)

| Key | Reference | Workbook 2 no. | `References.md` no. |
|---|---|---|---|
| Le 2020 | T. N. Le and Z. Liu, "Flex: Closing the gaps between usage and allocation," arXiv:2006.01354, 2020. | [1] | [1] |
| Chowdhury 2023 | Chowdhury *et al.*, "A deep dive into the Google cluster workload traces: Analyzing the application failure characteristics and user behaviors," arXiv:2308.02358, 2023. | [2] | [2] |
| Everman 2022 | B. Everman, M. Gao, and Z. Zong, "Evaluating and reducing cloud waste and cost—A data-driven case study from Azure workloads," *Sustain. Comput. Inform. Syst.*, vol. 35, p. 100708, 2022. | [3] | [3] |
| Sandholm 2015 | T. Sandholm, J. Ward, F. Balestrieri, and B. A. Huberman, "QoS-based pricing and scheduling of batch jobs in OpenStack clouds," arXiv:1504.07283, 2015. | [4] | [4] |
| Cortez 2017 | E. Cortez *et al.*, "Resource Central: Understanding and predicting workloads for improved resource management in large cloud platforms," in *Proc. ACM SOSP*, 2017. | [5] | [5] |
| Wilkes 2019 | J. Wilkes *et al.*, "Google Borg cluster traces (ClusterData 2019)," 2019. https://github.com/google/cluster-data | [6] | [6] |
| Kaggle subset | Google 2019 cluster sample, Kaggle. https://www.kaggle.com/datasets/derrickmwiti/google-2019-cluster-sample | [7] | — |
| Azure datasets | Microsoft Azure public datasets (VM, LLM inference, multimodal traces). | [8] | — |
| Splitwise 2024 | Splitwise (LLM inference phase splitting) and its Azure LLM inference traces. | [9] | — |
| ModServe 2025 | ModServe (stage-aware multimodal serving) and its Azure multimodal traces. | [10] | — |
| Jeon 2019 | M. Jeon *et al.*, "Analysis of large-scale multi-tenant GPU clusters for DNN training workloads," in *Proc. USENIX ATC*, 2019. | [11] | [7] |
| Liu 2023 | Y. Liu, H. Xu, and W. C. Lau, "Cloud configuration optimization for recurring batch-processing applications" (Accordia), *IEEE TPDS*, 2023. | [12] | [11] |
| Huang 2023 | N. Huang, A. Li, S. Zhang, and Z. Zong, "Reducing cloud expenditures and carbon emissions via virtual machine migration and downsizing," in *Proc. IEEE IPCCC*, 2023. | [13] / [14] (see note) | [12] |
| Scheinert 2021 | R. Scheinert *et al.*, "On the potential of execution traces for batch processing workload optimization in public clouds," arXiv:2111.08759, 2021. | [14] | [9] |
| Wang 2025 | Y. Wang *et al.*, "A tail latency SLO guaranteed task scheduling scheme for user-facing services" (TailGuard), *IEEE TPDS*, 2025. | [15] | [13] |
| Alipourfard 2017 | O. Alipourfard *et al.*, "CherryPick: Adaptively unearthing the best cloud configurations for big data analytics," in *Proc. USENIX NSDI*, 2017. | [16] | [14] |
| Tyagi 2023 | S. Tyagi and P. Sharma, "Scavenger: A cloud service for optimizing cost and performance of ML training," arXiv:2303.06659, 2023. | [17] | [15] |
| Alibaba 2020 | Alibaba Group, "Alibaba Cluster Trace Program," https://github.com/alibaba/clusterdata (cluster-trace-gpu-v2020). | — | [8] |

**Notes for the rewritten literature review** (from the Workbook 2 version):
1. **[4] is used for two different works.** It is the QoS-based pricing paper (Sandholm 2015), but the text also cites [4] for "backfilling with system-generated predictions" in HPC, which is a different paper not in the list.
2. **[13] and [14] are each used for two works.** [13] is cited for "HPC trace studies" and for Azure downsizing; [14] for trace-driven workload optimization and, at the end of §1.2, for Azure downsizing.
3. **Splitwise and ModServe** need full bibliographic entries (authors, venue, year).
4. **Alibaba GPU 2020** is not in the Workbook 2 review. Its README asks users to cite the trace paper (see B1 below).

---

## B. Candidate references for the rewritten review: not cited until a team member has read them

Chapter 4 marks each place that needs one of these with **[CITATION NEEDED: …]**. A candidate moves to section A only after someone has read it and confirmed it supports the claim. Check the details against the publisher before adding.

| # | Candidate | Claim it would support (Chapter 4 location) |
|---|---|---|
| B1 | Q. Weng *et al.*, "MLaaS in the wild: Workload analysis and scheduling in large-scale heterogeneous GPU clusters," USENIX NSDI 2022 | Official Alibaba GPU 2020 trace paper; role heterogeneity (4.1) |
| B2 | M. Tirmazi *et al.*, "Borg: The next generation," EuroSys 2020; A. Verma *et al.*, "Large-scale cluster management at Google with Borg," EuroSys 2015 | Official ClusterData 2019 paper; Borg job and task model (4.1) |
| B3 | K. Rzadca *et al.*, "Autopilot: Workload autoscaling at Google," EuroSys 2020; Kubernetes Vertical Pod Autoscaler documentation | Production autoscalers size from usage percentiles (4.2.1) |
| B4 | S. Kaufman *et al.*, "Leakage in data mining: Formulation, detection, and avoidance," ACM TKDD 2012 | Leakage (4.1, 4.2.2) |
| B5 | C. Bergmeir and J. M. Benítez, "On the use of cross-validation for time series predictor evaluation," Information Sciences 2012 | Cross-validation for time-ordered data (4.1) |
| B6 | C. Reiss *et al.*, "Heterogeneity and dynamicity of clouds at scale: Google trace analysis," ACM SoCC 2012 | Non-stationarity of cluster workloads (4.1) |
| B7 | A. N. Angelopoulos and S. Bates, "A gentle introduction to conformal prediction and distribution-free uncertainty quantification," arXiv:2107.07511, 2021 | Order-statistic coverage argument (4.2.1) |
| B8 | L. Breiman *et al.*, *Classification and Regression Trees*, 1984; L. Breiman, "Random forests," Machine Learning 2001 | Decision tree and random forest (4.2.2) |
| B9 | T. Chen and C. Guestrin, "XGBoost," KDD 2016; G. Ke *et al.*, "LightGBM," NeurIPS 2017 | Gradient boosting (4.2.2) |
| B10 | L. Grinsztajn, E. Oyallon, and G. Varoquaux, "Why do tree-based models still outperform deep learning on typical tabular data?" NeurIPS 2022 | Trees vs deep learning on tabular data (4.2.2) |
| B11 | N. Duan, "Smearing estimate: A nonparametric retransformation method," JASA 1983 | Back-transformation bias of `log1p` (4.2.2) |
| B12 | M. López de Prado, *Advances in Financial Machine Learning*, Wiley 2018 | Purged cross-validation (4.2.2) |
| B13 | R. Koenker and G. Bassett, "Regression quantiles," Econometrica 1978 | Quantile regression alternative (4.2.2) |
| B14 | C. Dwork *et al.*, "The reusable holdout: Preserving validity in adaptive data analysis," Science 2015 | Overfitting from repeated use of evaluation data (4.2.3, 4.3) |
| B15 | G. K. Sandve *et al.*, "Ten simple rules for reproducible computational research," PLoS Comput. Biol. 2013 | Reproducibility practices (4.4) |
| B16 | F. Pedregosa *et al.*, "Scikit-learn: Machine learning in Python," JMLR 2011 | scikit-learn (Chapter 3) |
