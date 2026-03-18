function plot_H2O_NIR()
    %==========================
    % 参数设置
    %==========================
    parFile = 'D:\Desktop\111\吸收光谱\h2o_69847fa9.par';    % 你的 HITRAN .par 文件名

    lambda_min_nm = 1000;            % 波长下限 (nm)
    lambda_max_nm = 2000;            % 波长上限 (nm)

    % 由波长范围换算波数范围（cm^-1）
    nu_max = 1e7 / lambda_min_nm;    % 对应 1000 nm → 10000 cm^-1
    nu_min = 1e7 / lambda_max_nm;    % 对应 2000 nm →  5000 cm^-1

    % 计算网格：在波数上均匀采样，再转换为波长
    dnu = 0.01;                      % 波数步长 (cm^-1)，可根据需求调节
    nu_grid = (nu_min:dnu:nu_max).'; % 列向量
    Nnu = numel(nu_grid);

    %==========================
    % 读取 HITRAN .par 文件
    %==========================
    fprintf('Reading HITRAN file: %s\n', parFile);

    % HITRAN2004 格式说明 (前面部分)：
    %  1- 2: molec_id (I2)
    %  3:   local_iso_id (I1)
    %  4-15: nu (F12.6)
    % 16-25: sw (E10.3)
    % 26-35: a (F10.4, 或 5.4/10.4 视版本而定)
    % 后面还有多个字段，这里不逐一用。
    %
    % 为了稳妥，采用文本行解析方式，而不是 'textscan' 的固定宽度。
    
    fid = fopen(parFile, 'r');
    if fid < 0
        error('无法打开文件：%s', parFile);
    end

    molID   = [];
    isoID   = [];
    nu      = [];
    S       = [];
    gamma_air = [];

    lineCount = 0;
    while true
        tline = fgetl(fid);
        if ~ischar(tline)
            break;
        end
        lineCount = lineCount + 1;

        % 行长度不足则跳过
        if length(tline) < 45
            continue;
        end

        try
            % 按 HITRAN2004 规范位置截取
            % 注意：MATLAB 下索引要手工调，以下区间略宽一点，避免因格式微差报错
            mol_str   = strtrim(tline(1:2));
            iso_str   = strtrim(tline(3:3));
            nu_str    = strtrim(tline(4:15));
            S_str     = strtrim(tline(16:25));
            % γ_air 的宽度在不同说明中略有差异，取 26:35 一般可覆盖
            gamma_str = strtrim(tline(26:35));

            molID_val   = str2double(mol_str);
            isoID_val   = str2double(iso_str);
            nu_val      = str2double(nu_str);
            S_val       = str2double(S_str);
            gamma_val   = str2double(gamma_str);

            % 防止 NaN
            if isnan(molID_val) || isnan(isoID_val) || isnan(nu_val) || isnan(S_val) || isnan(gamma_val)
                continue;
            end

            molID   = [molID;   molID_val];
            isoID   = [isoID;   isoID_val];
            nu      = [nu;      nu_val];
            S       = [S;       S_val];
            gamma_air = [gamma_air; gamma_val];

        catch ME
            warning('第 %d 行解析失败: %s', lineCount, ME.message);
            continue;
        end
    end
    fclose(fid);

    fprintf('总共读取 %d 条谱线\n', numel(nu));

    %==========================
    % 选择 H2O (H2-16-O) 且在 5000–10000 cm^-1 范围内的线
    %==========================
    % HITRAN: molID=1 → H2O
    % local_iso_id=1 → H2-16-O
    mask = (molID == 1) & (isoID == 1) & (nu >= nu_min) & (nu <= nu_max) & (S > 0);
    nu_h2o    = nu(mask);
    S_h2o     = S(mask);
    gamma_h2o = gamma_air(mask);

    fprintf('选中 H2O H2-16-O 线数：%d 条\n', numel(nu_h2o));

    if isempty(nu_h2o)
        error('在给定波数范围内未找到 H2O (H2-16-O) 的谱线，请检查波段/文件。');
    end

    %==========================
    % 构建 Lorentz 吸收谱
    %==========================
    fprintf('计算吸收谱...\n');

    alpha_nu = zeros(Nnu, 1);  % 吸收系数（单位 ~ S/cm^-1，未乘浓度、路径）

    % 为避免巨慢，适当矢量化 + 限制每条线计算宽度
    % 例如只在 |nu - nu_i| < 10*gamma 的范围内叠加
    halfWidthFactor = 10;  % 线外 10*γ 之外贡献极小，可忽略

    for i = 1:numel(nu_h2o)
        nu0 = nu_h2o(i);
        S_i = S_h2o(i);
        g_i = gamma_h2o(i);

        if g_i <= 0
            continue;
        end

        % 限定本线计算范围
        nu_min_i = nu0 - halfWidthFactor * g_i;
        nu_max_i = nu0 + halfWidthFactor * g_i;

        idx = (nu_grid >= nu_min_i) & (nu_grid <= nu_max_i);
        if ~any(idx)
            continue;
        end

        dnu_i = nu_grid(idx) - nu0;

        % 标准洛伦兹线型（归一化 ∫L dnu = 1）
        L_i = (1/pi) * (g_i ./ (dnu_i.^2 + g_i.^2));

        alpha_nu(idx) = alpha_nu(idx) + S_i .* L_i;
    end

    %==========================
    % 转换到波长轴并作图
    %==========================
    % 波长 λ (nm) = 1e7 / ν (cm^-1)
    lambda_nm = 1e7 ./ nu_grid;

    % 为了顺眼，按波长从小到大排序
    [lambda_nm_sort, idx_sort] = sort(lambda_nm);
    alpha_lambda = alpha_nu(idx_sort);

    %==========================
    % 绘图
    %==========================
    figure;
    plot(lambda_nm_sort, alpha_lambda, 'b-');
    %set(gca, 'XDir','reverse'); % 常见做法：短波在左，长波在右
    xlabel('Wavelength (nm)');
    ylabel('Absorption coefficient (arb. units)');
    title('H_2O (H_2^{16}O) Absorption Spectrum, 1000–2000 nm');
    grid on;

    xlim([lambda_min_nm lambda_max_nm]); % 限定在 1000–2000 nm

    fprintf('绘图完成。\n');
end
