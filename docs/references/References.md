## **References**

1. Le, T. N., & Liu, Z. Flex: Closing the Gaps between Usage and Allocation. (2020). arXiv:2006.01354. Retrieved February 25, 2026,  
   from [https://arxiv.org/abs/2006.01354](https://arxiv.org/abs/2006.01354?utm_source=chatgpt.com)

\[Academic\] Uses Google cluster traces to show persistent gaps between requested and used resources and proposes a runtime manager to exploit slack. Motivates TraceAdvisor by demonstrating that over-provisioning is systematic and measurable from traces.

2. Chowdhury, et al. A Deep Dive into the Google Cluster Workload Traces: Analyzing the Application Failure Characteristics and User Behaviors. (2023). arXiv:2308.02358. Retrieved February 25, 2026,  
   from [https://arxiv.org/abs/2308.02358](https://arxiv.org/abs/2308.02358?utm_source=chatgpt.com)

\[Academic\] Large-scale analysis of Google ClusterData2019 emphasizing failure/killed-job characteristics and user behaviors. Supports the premise that production traces capture repeatable signals relevant to resource decisions.

3. Everman, B., Gao, M., & Zong., *Evaluating and reducing cloud waste and cost—A data-driven case study from Azure workloads.* (2022). S*ustainable Computing: Informatics and Systems, vol. 35, p. 100708\.* Retrieved February 25, 2026 

from [doi: 10.1016/j.suscom.2022.100708](https://doi.org/10.1016/j.suscom.2022.100708)

\[Academic\] Empirical study of Azure production workloads quantifying persistent underutilization and cloud waste. Provides evidence that systematic over provisioning extended beyond Google clusters.

4. Sandholm, T., Ward, J., Balestrieri, F., & Huberman, B. A. QoS-Based Pricing and Scheduling of Batch Jobs in OpenStack Clouds. (2015). arXiv:1504.07283. Retrieved February 25, 2026,  
   from [https://arxiv.org/abs/1504.07283](https://arxiv.org/abs/1504.07283?utm_source=chatgpt.com)

\[Academic\] Explains why users misestimate batch job requirements and over-provision under uncertainty. Supports TraceAdvisor’s motivation for pre-execution decision support.

5. Cortez, E., Bonde, A., Muzio, A., Moscibroda, T., Magalhaes, G., Russinovich, M., Fontoura, M., & Bianchini, R. Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms. (2017). ACM SOSP 2017\. Retrieved February 25, 2026,  
   from [https://dl.acm.org/doi/epdf/10.1145/3132747.3132772](https://dl.acm.org/doi/epdf/10.1145/3132747.3132772?utm_source=chatgpt.com)

\[Academic\] Comprehensive characterization of Microsoft Azure VM workloads and evidence that historical behavior can predict future behavior. Supports TraceAdvisor’s use of history for guidance on recurring workloads.

6. Wilkes, J., et al. Google Borg Cluster Traces (ClusterData2019) – dataset repository. (2019). Retrieved February 25, 2026,  
   from [https://github.com/google/cluster-data](https://github.com/google/cluster-data?utm_source=chatgpt.com)

\[Dataset\] Official Google repository describing Borg workload traces, including resource requests and utilization signals. Primary dataset foundation for TraceAdvisor’s job-level reconstruction, slack analysis, and evaluation.

7. Jeon, M., Venkataraman, S., Phanishayee, A., Qian, J., Xiao, W., & Yang, F. Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads. (2019). USENIX ATC 2019\. Retrieved February 25, 2026,  
   from [https://www.usenix.org/system/files/atc19-jeon.pdf](https://www.usenix.org/system/files/atc19-jeon.pdf?utm_source=chatgpt.com)

\[Academic\] Production GPU-cluster characterization highlighting utilization challenges, locality/gang scheduling effects, and failures. Supports TraceAdvisor’s motivation for peak/tail-aware guidance for ML training jobs.

8. Alibaba Group. Alibaba Cluster Trace Program – dataset repository. (2017–2025). Retrieved February 25, 2026,  
   from [https://github.com/alibaba/clusterdata](https://github.com/alibaba/clusterdata?utm_source=chatgpt.com)

\[Dataset\] Production trace program released by Alibaba across multiple versions. Used as an optional validation dataset and as supporting evidence that large-scale trace-based research is standard in industry.

9. Scheinert, R., et al. On the Potential of Execution Traces for Batch Processing Workload Optimization in Public Clouds. (2021). arXiv:2111.08759. Retrieved February 25, 2026,  
   from [https://arxiv.org/abs/2111.08759](https://arxiv.org/abs/2111.08759?utm_source=chatgpt.com)

\[Academic\] Argues execution traces enable offline workload optimization when online deployment/profiling is infeasible. Supports TraceAdvisor’s offline-first, trace-replay evaluation methodology.

10. Chang, T.-T., & Venkataraman, S. Eva: Cost-Efficient Cloud-Based Cluster Scheduling. (2025). arXiv:2503.07437. Retrieved February 25, 2026,  
    from [https://arxiv.org/abs/2503.07437](https://arxiv.org/abs/2503.07437?utm_source=chatgpt.com)

\[Academic\] Demonstrates that trace-driven simulation can credibly evaluate cost/performance tradeoffs at scale. Supports TraceAdvisor’s use of offline replay/simulation for impact estimation.

11. Liu, Y., Xu, H., & Lau, W. C. Cloud Configuration Optimization for Recurring Batch-Processing Applications. (2023). *IEEE Transactions on Parallel and Distributed Systems (TPDS)*. Retrieved February 25, 2026, 

from [https://doi.org/10.1109/TPDS.2023.3246086](https://doi.org/10.1109/TPDS.2023.3246086)

\[Academic\] Reviews Accordia, a recurrence-aware cloud configuration optimization framework for batch-processing workloads. It establishes a baseline for learning from recurring workload patterns through configuration search and online experimentation.

12. Huang, N., Li, A., Zhang, S., & Zong, Z. Reducing Cloud Expenditures and Carbon Emissions via Virtual Machine Migration and Downsizing. (2023). *2023 IEEE International Performance, Computing, and Communications Conference (IPCCC)*. Retrieved February 25, 2026, 

from [https://doi.org/10.1109/IPCCC59175.2023.10253871](https://doi.org/10.1109/IPCCC59175.2023.10253871)

\[Academic\] Presents percentile-guided framework for identifying wasteful VMs and reducing cloud costs through migration and conservative downsizing. Study leverages P95 style CPU metrics for safe resource reduction.

13. Wang, Y., et al. A Tail Latency SLO Guaranteed Task Scheduling Scheme for User-Facing Services (TailGuard line). (2025). IEEE Transactions on Parallel and Distributed Systems (TPDS). Retrieved February 25, 2026,  
    from [https://par.nsf.gov/servlets/purl/10638755](https://par.nsf.gov/servlets/purl/10638755?utm_source=chatgpt.com)

\[Academic\] Percentile/tail guarantees (e.g., P95/P99) for rare critical events are standard in production systems. TraceAdvisor adopts the same tail-aware philosophy for peak resource risk (OOM/eviction), rather than latency.

14. Alipourfard, O., Liu, H. H., Chen, J., Venkataraman, S., Yu, M., & Zhang, M. CherryPick: Adaptively Unearthing the Best Cloud Configurations for Big Data Analytics. (2017). USENIX NSDI 2017\. Retrieved February 25, 2026,  
    from [https://www.usenix.org/system/files/conference/nsdi17/nsdi17-alipourfard.pdf](https://www.usenix.org/system/files/conference/nsdi17/nsdi17-alipourfard.pdf?utm_source=chatgpt.com)

\[Academic\] Configuration recommendation via Bayesian optimization; establishes the value of decision-support systems and what-if exploration for cloud workload settings. Provides related-work grounding for TraceAdvisor’s advisory workflow.

15. Tyagi, S., & Sharma, P. Scavenger: A Cloud Service for Optimizing Cost and Performance of ML Training. (2023). arXiv:2303.06659. Retrieved February 25, 2026,  
    from [https://arxiv.org/abs/2303.06659](https://arxiv.org/abs/2303.06659?utm_source=chatgpt.com)

\[Academic\] Model-based optimization for distributed ML training configurations using online search. Closest in spirit to TraceAdvisor; TraceAdvisor differs by using offline traces and focusing on safe-minimum resource requests with explicit risk control.