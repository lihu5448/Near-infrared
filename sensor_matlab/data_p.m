
%   将测量电压与参考电压的值对齐
function protocolData = parseVoltageProtocol()
    % 解析电压数据协议 - 处理十六进制字符串格式
    % 协议格式:
    % [0x5A] [0xA5] [TYPE] [DATA0] [DATA1] [DATA2] [DATA3] [CHECKSUM] [0x0D] [0x0A]
    %
    % ========== 对齐算法说明 ==========
    % 测量光(0x01)与参考光(0x02)传感器在机械结构上相差45°
    % 对齐策略（两步法）：
    %   Step1 固定偏移：offset_fixed = round(45/360 * N)
    %   Step2 互相关精校正：在 [offset_fixed ± SEARCH_WINDOW] 窗口内
    %         搜索互相关峰值，得到 offset_refined
    %   最终将参考光序列循环移位 offset_refined 个点，
    %   截取前 N - offset_refined 个点作为有效对齐段输出
    % ====================================

    % ==================== 全局路径设置 ====================
    DATA_FOLDER   = 'D:\Desktop\sensor_data\';
    OUTPUT_FOLDER = 'D:\Desktop\sensor_matlab\process_output\';
    INPUT_FILE    = '6.23_1.txt';

    % ==================== 湿度数据设置 ====================
    HUMIDITY_DATA = '6.23%';

    humidity_value      = strrep(HUMIDITY_DATA, '%', '');
    MEASURE_OUTPUT_FILE = sprintf('measure_%s.txt',  humidity_value);
    REFER_OUTPUT_FILE   = sprintf('refer_%s.txt',    humidity_value);
    ALIGNED_OUTPUT_FILE = sprintf('aligned_%s.txt',  humidity_value);

    inputFilePath   = fullfile(DATA_FOLDER,   INPUT_FILE);
    measureFilePath = fullfile(OUTPUT_FOLDER, MEASURE_OUTPUT_FILE);
    referFilePath   = fullfile(OUTPUT_FOLDER, REFER_OUTPUT_FILE);
    alignedFilePath = fullfile(OUTPUT_FOLDER, ALIGNED_OUTPUT_FILE);

    fprintf('=== 文件路径设置 ===\n');
    fprintf('输入文件:     %s\n', inputFilePath);
    fprintf('测量光输出:   %s\n', measureFilePath);
    fprintf('参考光输出:   %s\n', referFilePath);
    fprintf('对齐数据输出: %s\n', alignedFilePath);
    fprintf('湿度数据:     %s\n', HUMIDITY_DATA);
    fprintf('========================\n\n');

    if ~exist(inputFilePath, 'file')
        error('文件不存在: %s', inputFilePath);
    end

    fprintf('正在读取文件: %s\n', inputFilePath);
    try
        fileID = fopen(inputFilePath, 'r');
        if fileID == -1, error('无法打开文件'); end
        textContent = fscanf(fileID, '%c');
        fclose(fileID);
        fprintf('文件读取成功，文本长度: %d 字符\n', length(textContent));
    catch ME
        error('文件读取失败: %s', ME.message);
    end

    rawData      = hexStringToBinary(textContent);
    protocolData = parseVoltagePackets(rawData);
    protocolData = calculateStatistics(protocolData);
    protocolData = alignMeasureRefer(protocolData);

    displayVoltageResults(protocolData);
    plotVoltageData(protocolData);
    saveVoltageDataToFiles(protocolData, measureFilePath, referFilePath, ...
                           alignedFilePath, HUMIDITY_DATA);
end

% =========================================================
%  十六进制字符串 → 二进制数组
% =========================================================
function rawData = hexStringToBinary(textContent)
    cleanText = regexprep(textContent, '\s', '');
    if mod(length(cleanText), 2) ~= 0
        warning('十六进制字符串长度不是偶数，截断处理');
        cleanText = cleanText(1:end-1);
    end
    dataLength = length(cleanText) / 2;
    rawData    = zeros(1, dataLength, 'uint8');
    for i = 1:dataLength
        rawData(i) = hex2dec(cleanText((i-1)*2+1 : i*2));
    end
    fprintf('十六进制转换完成，得到 %d 字节\n', dataLength);
    if dataLength > 0
        fprintf('前100字节: ');
        for i = 1:min(100, dataLength)
            fprintf('%02X ', rawData(i));
        end
        if dataLength > 100, fprintf('...'); end
        fprintf('\n');
    end
end

% =========================================================
%  协议包解析
% =========================================================
function protocolData = parseVoltagePackets(rawData)
    START1      = hex2dec('5A');
    START2      = hex2dec('A5');
    END1        = hex2dec('0D');
    END2        = hex2dec('0A');
    PACKET_SIZE = 10;
    TYPE_NOTHING = hex2dec('00');
    TYPE_MEASURE = hex2dec('01');
    TYPE_REFER   = hex2dec('02');
    INVALID_1    = uint8([0x00,0x00,0x00,0x00]);
    INVALID_2    = uint8([0xFF,0xFF,0xFF,0xFF]);

    protocolData = struct();
    protocolData.packets            = {};
    protocolData.validPacketCount   = 0;
    protocolData.corruptedPackets   = 0;
    protocolData.invalidDataPackets = 0;
    protocolData.voltageValues      = [];
    protocolData.packetTypes        = [];
    protocolData.measureCount       = 0;
    protocolData.referCount         = 0;
    protocolData.nothingCount       = 0;
    protocolData.measureVoltages    = [];
    protocolData.referVoltages      = [];

    i               = 1;
    packetCount     = 0;
    corruptedCount  = 0;
    invalidCount    = 0;
    voltageValues   = [];
    packetTypes     = [];
    measureCount    = 0;
    referCount      = 0;
    nothingCount    = 0;
    measureVoltages = [];
    referVoltages   = [];

    while i <= length(rawData) - PACKET_SIZE + 1
        if rawData(i)   == START1 && rawData(i+1) == START2 && ...
           rawData(i+8) == END1   && rawData(i+9) == END2
            packet    = rawData(i:i+PACKET_SIZE-1);
            dataType  = packet(3);
            dataBytes = packet(4:7);
            chkRecv   = packet(8);
            chkCalc   = mod(sum(packet(4:7)), 256);
            chkOK     = (chkRecv == chkCalc);
            isInvalid = isequal(dataBytes, INVALID_1) || isequal(dataBytes, INVALID_2);

            voltageInt = typecast(uint8([packet(4),packet(5),packet(6),packet(7)]), 'int32');
            voltage    = double(voltageInt) / 1e6;

            packetCount = packetCount + 1;
            switch dataType
                case TYPE_MEASURE
                    measureCount = measureCount + 1; typeStr = '测量光';
                    if chkOK && ~isInvalid
                        measureVoltages(end+1) = voltage; %#ok<AGROW>
                    end
                case TYPE_REFER
                    referCount = referCount + 1; typeStr = '参考光';
                    if chkOK && ~isInvalid
                        referVoltages(end+1) = voltage; %#ok<AGROW>
                    end
                case TYPE_NOTHING
                    nothingCount = nothingCount + 1; typeStr = '无类型';
                otherwise
                    typeStr = '未知类型';
            end

            protocolData.packets{packetCount} = struct( ...
                'rawData',            packet,      ...
                'startIndex',         i,           ...
                'dataType',           dataType,    ...
                'dataTypeStr',        typeStr,     ...
                'dataBytes',          dataBytes,   ...
                'receivedChecksum',   chkRecv,     ...
                'calculatedChecksum', chkCalc,     ...
                'checksumValid',      chkOK,       ...
                'isInvalidData',      isInvalid,   ...
                'voltageInt',         voltageInt,  ...
                'voltage',            voltage,     ...
                'dataValid',          chkOK && ~isInvalid);

            if chkOK && ~isInvalid
                voltageValues(end+1) = voltage; %#ok<AGROW>
                packetTypes(end+1)   = dataType; %#ok<AGROW>
            end
            if ~chkOK,    corruptedCount = corruptedCount + 1; end
            if isInvalid, invalidCount   = invalidCount   + 1; end
            i = i + PACKET_SIZE;
        else
            i = i + 1;
        end
    end

    protocolData.validPacketCount   = packetCount;
    protocolData.corruptedPackets   = corruptedCount;
    protocolData.invalidDataPackets = invalidCount;
    protocolData.voltageValues      = voltageValues;
    protocolData.packetTypes        = packetTypes;
    protocolData.measureCount       = measureCount;
    protocolData.referCount         = referCount;
    protocolData.nothingCount       = nothingCount;
    protocolData.measureVoltages    = measureVoltages;
    protocolData.referVoltages      = referVoltages;

    fprintf('协议解析完成:\n');
    fprintf('  有效数据包: %d\n',  packetCount);
    fprintf('  校验和错误: %d\n',  corruptedCount);
    fprintf('  无效数据值: %d\n',  invalidCount);
    fprintf('  测量光=%d  参考光=%d  无类型=%d\n', ...
        measureCount, referCount, nothingCount);
end

% =========================================================
%  统计信息
% =========================================================
function protocolData = calculateStatistics(protocolData)
    function s = calcStat(v)
        if ~isempty(v)
            s = struct('min',min(v),'max',max(v),'mean',mean(v),'std',std(v));
        else
            s = struct('min',NaN,'max',NaN,'mean',NaN,'std',NaN);
        end
    end
    protocolData.measure_stats = calcStat(protocolData.measureVoltages);
    protocolData.refer_stats   = calcStat(protocolData.referVoltages);
end

% =========================================================
%  ★ 45° 机械偏移对齐核心函数
% =========================================================
function protocolData = alignMeasureRefer(protocolData)
    MECH_ANGLE_DEG = 45;
    SEARCH_WINDOW  = 5;

    mV = protocolData.measureVoltages;
    rV = protocolData.referVoltages;

    % 默认空结果
    protocolData.alignOffset      = 0;
    protocolData.alignOffsetFixed = 0;
    protocolData.alignAngleDeg    = 0;
    protocolData.measureAligned   = mV;
    protocolData.referAligned     = rV;
    protocolData.alignValidLen    = min(length(mV), length(rV));
    protocolData.alignPearsonR    = NaN;
    protocolData.stepAngleDeg     = 0;

    if isempty(mV) || isempty(rV)
        warning('对齐跳过：测量光或参考光数据为空');
        return;
    end

    N = min(length(mV), length(rV));

    % 每点对应角度（步长）
    stepAngle = 360.0 / N;

    % Step1：固定偏移
    offset_fixed = round(MECH_ANGLE_DEG / 360.0 * N);

    fprintf('\n=== 45° 机械偏移对齐 ===\n');
    fprintf('  序列长度 N = %d，步长 = %.2f°/点\n', N, stepAngle);
    fprintf('  Step1 固定偏移 = %d 点 (%.2f°)\n', offset_fixed, offset_fixed*stepAngle);

    % Step2：互相关精校正
    m_seg = mV(1:N) - mean(mV(1:N));
    r_seg = rV(1:N) - mean(rV(1:N));
    [xc, lags] = xcorr(r_seg, m_seg, N-1, 'normalized');

    lo   = max(0,   offset_fixed - SEARCH_WINDOW);
    hi   = min(N-1, offset_fixed + SEARCH_WINDOW);
    mask = (lags >= lo) & (lags <= hi);

    if any(mask)
        [~, idx]       = max(xc(mask));
        valid_lags     = lags(mask);
        offset_refined = valid_lags(idx);
    else
        warning('互相关搜索窗口内无有效滞后，退回固定偏移');
        offset_refined = offset_fixed;
    end

    fprintf('  Step2 精校正偏移 = %d 点 (%.2f°)  搜索窗口 [%d, %d]\n', ...
        offset_refined, offset_refined*stepAngle, lo, hi);

    % Step3：循环移位 + 截取有效段
    rV_shifted = circshift(rV(1:N), -offset_refined);
    valid_len  = N - abs(offset_refined);
    m_aligned  = mV(1:valid_len);
    r_aligned  = rV_shifted(1:valid_len);

    pearson_r = corr(m_aligned(:), r_aligned(:));

    fprintf('  最终偏移 = %d 点 (%.2f°)\n', offset_refined, offset_refined*stepAngle);
    fprintf('  有效对齐点数 = %d\n', valid_len);
    fprintf('  对齐后 Pearson r = %.4f\n', pearson_r);
    fprintf('========================\n\n');

    protocolData.alignOffset      = offset_refined;
    protocolData.alignOffsetFixed = offset_fixed;
    protocolData.alignAngleDeg    = offset_refined * stepAngle;
    protocolData.measureAligned   = m_aligned;
    protocolData.referAligned     = r_aligned;
    protocolData.alignValidLen    = valid_len;
    protocolData.alignPearsonR    = pearson_r;
    protocolData.stepAngleDeg     = stepAngle;
    protocolData.N                = N;
end

% =========================================================
%  显示解析结果
% =========================================================
function displayVoltageResults(protocolData)
    fprintf('\n=== 电压数据协议解析结果 ===\n');
    fprintf('有效数据包:   %d\n', protocolData.validPacketCount);
    fprintf('校验和错误:   %d\n', protocolData.corruptedPackets);
    fprintf('无效数据值:   %d\n', protocolData.invalidDataPackets);
    fprintf('数据类型统计:\n');
    fprintf('  测量光(0x01): %d\n', protocolData.measureCount);
    fprintf('  参考光(0x02): %d\n', protocolData.referCount);
    fprintf('  无类型(0x00): %d\n', protocolData.nothingCount);

    if ~isempty(protocolData.measureVoltages)
        fprintf('\n=== 测量光统计 ===\n');
        fprintf('  Min=%.6fV  Max=%.6fV  Mean=%.6fV  Std=%.6fV  N=%d\n', ...
            protocolData.measure_stats.min, protocolData.measure_stats.max, ...
            protocolData.measure_stats.mean,protocolData.measure_stats.std, ...
            length(protocolData.measureVoltages));
    end
    if ~isempty(protocolData.referVoltages)
        fprintf('\n=== 参考光统计 ===\n');
        fprintf('  Min=%.6fV  Max=%.6fV  Mean=%.6fV  Std=%.6fV  N=%d\n', ...
            protocolData.refer_stats.min, protocolData.refer_stats.max, ...
            protocolData.refer_stats.mean,protocolData.refer_stats.std, ...
            length(protocolData.referVoltages));
    end

    fprintf('\n=== 对齐结果 ===\n');
    fprintf('  固定偏移(45°先验): %d 点\n',  protocolData.alignOffsetFixed);
    fprintf('  精校正偏移:        %d 点 (%.2f°)\n', ...
        protocolData.alignOffset, protocolData.alignAngleDeg);
    fprintf('  有效对齐点数:      %d\n',    protocolData.alignValidLen);
    fprintf('  对齐后 Pearson r:  %.4f\n',  protocolData.alignPearsonR);

    if protocolData.validPacketCount > 0
        fprintf('\n数据包详情（前20条）:\n');
        fprintf('%-6s %-8s %-12s %-15s %-12s %s\n', ...
            '序号','类型','整数值','电压值(V)','校验和','状态');
        fprintf('%s\n', repmat('-',1,70));
        for i = 1:min(20, protocolData.validPacketCount)
            p = protocolData.packets{i};
            if p.checksumValid && ~p.isInvalidData, st = '✓ 有效';
            elseif ~p.checksumValid,                st = '✗ 校验和错误';
            else,                                   st = '✗ 无效数据值';
            end
            fprintf('%-6d %-8s %-12d %-15.6f 0x%02X/0x%02X %s\n', ...
                i, p.dataTypeStr, p.voltageInt, p.voltage, ...
                p.receivedChecksum, p.calculatedChecksum, st);
        end
        if protocolData.validPacketCount > 20
            fprintf('... (仅显示前20条)\n');
        end
    end
end

% =========================================================
%  ★ 绘图 —— 仿附件6子图布局
% =========================================================
function plotVoltageData(protocolData)
    if protocolData.validPacketCount < 2, return; end

    mV      = protocolData.measureVoltages;   % 测量光原始
    rV      = protocolData.referVoltages;     % 参考光原始
    N       = protocolData.N;
    off     = protocolData.alignOffset;
    stepDeg = protocolData.stepAngleDeg;

    % ── X 轴角度 ─────────────────────────────────────────
    angles_m   = (0 : length(mV)-1) * stepDeg;
    angles_r   = (0 : length(rV)-1) * stepDeg;
    angles_N   = linspace(0, 360, N);

    % ── 参考光循环移位对齐 ────────────────────────────────
    rV_shifted = circshift(rV(1:N), -off);

    % ── 颜色 ─────────────────────────────────────────────
    C_M = [0.85, 0.15, 0.15];   % 红 — 测量光
    C_R = [0.20, 0.45, 0.80];   % 蓝 — 参考光原始
    C_A = [0.10, 0.65, 0.25];   % 绿 — 参考光对齐后

    % ── 创建图窗 ─────────────────────────────────────────
    fig = figure('Color','white','Position',[50, 50, 1400, 780]);

    % 总标题
    annotation(fig,'textbox',[0, 0.95, 1, 0.05], ...
        'String',{ ...
            'NIR 水分仪旋转一圈原始 ADC 波形  |  物理角度对齐', ...
            sprintf('测量光 → 参考光  物理偏差 45°，对应 %d 个采样点（步长 %.2f°/点）', ...
                off, stepDeg)}, ...
        'HorizontalAlignment','center', ...
        'VerticalAlignment',  'middle', ...
        'FontSize',11,'FontWeight','bold', ...
        'EdgeColor','none','BackgroundColor','none');

    % =========================================================
    %  子图① — 测量光原始
    %  位置：左上，占上半行左侧
    % =========================================================
    ax1 = subplot('Position', [0.06, 0.54, 0.40, 0.36]);
    plot(angles_m, mV, '-o', ...
        'Color',C_M,'LineWidth',1.5, ...
        'MarkerSize',3,'MarkerFaceColor',C_M);
    title('① 测量光 (Measure) — 原始', ...
          'FontSize',10,'FontWeight','bold');
    xlabel('旋转角度 (°)','FontSize',9);
    ylabel('ADC 电压 (V)','FontSize',9);
    xlim([0, 360]); xticks(0:45:360);
    grid on; box on;
    set(ax1,'Color','white','GridColor',[0.85,0.85,0.85], ...
            'FontSize',9,'TickDir','out','LineWidth',0.8);

    % =========================================================
    %  子图② — 参考光原始（未对齐）
    %  位置：右上，占上半行右侧
    % =========================================================
    ax2 = subplot('Position', [0.55, 0.54, 0.40, 0.36]);
    plot(angles_r, rV, '-s', ...
        'Color',C_R,'LineWidth',1.5, ...
        'MarkerSize',3,'MarkerFaceColor',C_R);
    title('② 参考光 (Reference) — 原始（未对齐）', ...
          'FontSize',10,'FontWeight','bold');
    xlabel('旋转角度 (°)','FontSize',9);
    ylabel('ADC 电压 (V)','FontSize',9);
    xlim([0, 360]); xticks(0:45:360);
    grid on; box on;
    set(ax2,'Color','white','GridColor',[0.85,0.85,0.85], ...
            'FontSize',9,'TickDir','out','LineWidth',0.8);

    % =========================================================
    %  子图⑥ — 单Y轴叠加（测量光 + 参考光对齐后）
    %  位置：下半行，独占全宽
    % =========================================================
    ax6 = subplot('Position', [0.30, 0.08, 0.40, 0.36]);

    plot(angles_N, mV(1:N), '-o', ...
        'Color',C_M,'LineWidth',1.5, ...
        'MarkerSize',3,'MarkerFaceColor',C_M, ...
        'DisplayName','测量光'); hold on;

    plot(angles_N, rV_shifted, '-o', ...
        'Color',C_A,'LineWidth',1.5, ...
        'MarkerSize',3,'MarkerFaceColor',C_A, ...
        'DisplayName',sprintf('参考光对齐后（移位 +%d 点 ≈ 45°）', off));

    title('⑥ 原始光强值（原始值，单Y轴）', ...
          'FontSize',10,'FontWeight','bold');
    xlabel('旋转角度 (°)','FontSize',9);
    ylabel('ADC 电压 (V)','FontSize',9);
    xlim([0, 360]); xticks(0:45:360);
    legend('Location','northeast','FontSize',9,'Box','off');
    grid on; box on;
    set(ax6,'Color','white','GridColor',[0.85,0.85,0.85], ...
            'FontSize',9,'TickDir','out','LineWidth',0.8);
end


% =========================================================
%  保存数据
% =========================================================
function saveVoltageDataToFiles(protocolData, measureFilePath, ...
                                referFilePath, alignedFilePath, humidityData)
    % ── 保存测量光 ────────────────────────────────────────
    if ~isempty(protocolData.measureVoltages)
        fid = fopen(measureFilePath, 'w');
        if fid == -1, error('无法创建: %s', measureFilePath); end
        fprintf(fid, '# Humidity: %s\n',    humidityData);
        fprintf(fid, '# Min: %.6f V\n',     protocolData.measure_stats.min);
        fprintf(fid, '# Max: %.6f V\n',     protocolData.measure_stats.max);
        fprintf(fid, '# Mean: %.6f V\n',    protocolData.measure_stats.mean);
        fprintf(fid, '# Std: %.6f V\n',     protocolData.measure_stats.std);
        fprintf(fid, '# Count: %d\n#\n',    length(protocolData.measureVoltages));
        for i = 1:protocolData.validPacketCount
            p = protocolData.packets{i};
            if p.checksumValid && ~p.isInvalidData && p.dataType == hex2dec('01')
                fprintf(fid, '%.6f\n', p.voltage);
            end
        end
        fclose(fid);
        fprintf('测量光保存: %s\n', measureFilePath);
    end

    % ── 保存参考光 ────────────────────────────────────────
    if ~isempty(protocolData.referVoltages)
        fid = fopen(referFilePath, 'w');
        if fid == -1, error('无法创建: %s', referFilePath); end
        fprintf(fid, '# Humidity: %s\n',    humidityData);
        fprintf(fid, '# Min: %.6f V\n',     protocolData.refer_stats.min);
        fprintf(fid, '# Max: %.6f V\n',     protocolData.refer_stats.max);
        fprintf(fid, '# Mean: %.6f V\n',    protocolData.refer_stats.mean);
        fprintf(fid, '# Std: %.6f V\n',     protocolData.refer_stats.std);
        fprintf(fid, '# Count: %d\n#\n',    length(protocolData.referVoltages));
        for i = 1:protocolData.validPacketCount
            p = protocolData.packets{i};
            if p.checksumValid && ~p.isInvalidData && p.dataType == hex2dec('02')
                fprintf(fid, '%.6f\n', p.voltage);
            end
        end
        fclose(fid);
        fprintf('参考光保存: %s\n', referFilePath);
    end

    % ── 保存对齐后数据 ────────────────────────────────────
    if ~isempty(protocolData.measureAligned) && ~isempty(protocolData.referAligned)
        fid = fopen(alignedFilePath, 'w');
        if fid == -1, error('无法创建: %s', alignedFilePath); end
        fprintf(fid, '# Humidity: %s\n',                     humidityData);
        fprintf(fid, '# Alignment offset: %d pts (%.2f deg)\n', ...
            protocolData.alignOffset, protocolData.alignAngleDeg);
        fprintf(fid, '# Pearson r after alignment: %.4f\n',  protocolData.alignPearsonR);
        fprintf(fid, '# Valid aligned points: %d\n',         protocolData.alignValidLen);
        fprintf(fid, '# Columns: measure_voltage(V)  refer_voltage_aligned(V)\n#\n');
        for i = 1:protocolData.alignValidLen
            fprintf(fid, '%.6f\t%.6f\n', ...
                protocolData.measureAligned(i), protocolData.referAligned(i));
        end
        fclose(fid);
        fprintf('对齐数据保存: %s  (%d 对)\n', alignedFilePath, protocolData.alignValidLen);
    end

    fprintf('\n=== 保存汇总 ===\n');
    fprintf('  测量光有效数据: %d 条\n', length(protocolData.measureVoltages));
    fprintf('  参考光有效数据: %d 条\n', length(protocolData.referVoltages));
    fprintf('  对齐有效点对:   %d 对\n', protocolData.alignValidLen);
    fprintf('  过滤无效数据:   %d 条\n', ...
        protocolData.corruptedPackets + protocolData.invalidDataPackets);
end
