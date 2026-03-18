function protocolData = parseVoltageProtocol()
    % ==================== 全局路径设置 ====================
    DATA_FOLDER   = 'D:\Desktop\sensor_data\';
    OUTPUT_FOLDER = 'D:\Desktop\sensor_matlab\process_output\';
    DATE_PREFIX   = 'z';          % ← 只改这里，自动匹配所有 6.23_*.txt

    % ==================== 湿度数据设置 ====================
    HUMIDITY_DATA = 'z%';

    humidity_value = strrep(HUMIDITY_DATA, '%', '');

    fprintf('=== 批量处理：前缀 "%s" ===\n', DATE_PREFIX);

    % ── 自动搜索匹配文件 ─────────────────────────────────
    pattern  = fullfile(DATA_FOLDER, [DATE_PREFIX, '_*.txt']);
    fileList = dir(pattern);

    if isempty(fileList)
        error('未找到匹配文件：%s', pattern);
    end

    % 按文件名自然排序（_1 _2 _3 ...）
    [~, sortIdx] = sort({fileList.name});
    fileList = fileList(sortIdx);

    fprintf('共找到 %d 个文件：\n', numel(fileList));
    for k = 1:numel(fileList)
        fprintf('  [%d] %s\n', k, fileList(k).name);
    end
    fprintf('\n');

    % ── 逐文件处理 ───────────────────────────────────────
    allData = {};   % cell 数组，避免结构体字段不一致报错

    for k = 1:numel(fileList)
        fname        = fileList(k).name;
        inputPath    = fullfile(DATA_FOLDER, fname);
        [~, stem, ~] = fileparts(fname);   % e.g. '6.23_1'

        fprintf('==============================\n');
        fprintf('处理文件 [%d/%d]：%s\n', k, numel(fileList), fname);
        fprintf('==============================\n');

        % 读取
        fid = fopen(inputPath, 'r');
        if fid == -1, error('无法打开：%s', inputPath); end
        textContent = fscanf(fid, '%c');
        fclose(fid);

        % 解析
        rawData = hexStringToBinary(textContent);
        pd      = parseVoltagePackets(rawData);
        pd      = calculateStatistics(pd);
        pd      = alignMeasureRefer(pd);
        pd.fname = fname;
        pd.stem  = stem;

        displayVoltageResults(pd);

        % 保存单文件 txt
        mFile = fullfile(OUTPUT_FOLDER, sprintf('measure_%s_%s.txt',  humidity_value, stem));
        rFile = fullfile(OUTPUT_FOLDER, sprintf('refer_%s_%s.txt',    humidity_value, stem));
        aFile = fullfile(OUTPUT_FOLDER, sprintf('aligned_%s_%s.txt',  humidity_value, stem));
        saveVoltageDataToFiles(pd, mFile, rFile, aFile, HUMIDITY_DATA);

        allData{k} = pd;   % cell 数组赋值
    end

    % ── 汇总绘图 ─────────────────────────────────────────
    plotAllVoltageData(allData, DATE_PREFIX, HUMIDITY_DATA);

    protocolData = allData;
end


% =========================================================
%  汇总绘图：①②⑥ 三图，每图叠加所有文件的曲线
% =========================================================
function plotAllVoltageData(allData, datePrefix, humidityData)
    n = numel(allData);
    if n == 0, return; end

    % 颜色映射：每个文件一种颜色
    cmap = lines(n);

    % 创建一个新的图形窗口
    fig = figure('Color','white','Position',[50,50,800,600]);

    % 每个文件绘制一个图，排列在左侧
    for k = 1:n
        pd = allData{k};
        subplot(n, 2, (k-1)*2 + 1); % 测量光图
        hold on;
        if ~isempty(pd.measureVoltages)
            angles_m = (0:length(pd.measureVoltages)-1) * pd.stepAngleDeg;
            plot(angles_m, pd.measureVoltages, '-o', ...
                'Color',cmap(k,:),'LineWidth',1.2, ...
                'MarkerSize',2,'MarkerFaceColor',cmap(k,:), ...
                'DisplayName', pd.stem);
        end
        title(sprintf('文件 %d: 测量光 (Measure)', k),'FontSize',10,'FontWeight','bold');
        xlabel('旋转角度 (°)','FontSize',9);
        ylabel('ADC 电压 (V)','FontSize',9);
        xlim([0,360]); xticks(0:45:360);
        legend('Location','northeast','FontSize',8,'Box','off','NumColumns',1);
        grid on; box on;

        subplot(n, 2, (k-1)*2 + 2); % 参考光图
        hold on;
        if ~isempty(pd.referVoltages)
            angles_r = (0:length(pd.referVoltages)-1) * pd.stepAngleDeg;
            plot(angles_r, pd.referVoltages, '-s', ...
                'Color',cmap(k,:),'LineWidth',1.2, ...
                'MarkerSize',2,'MarkerFaceColor',cmap(k,:), ...
                'DisplayName', pd.stem);
        end
        title(sprintf('文件 %d: 参考光 (Reference)', k),'FontSize',10,'FontWeight','bold');
        xlabel('旋转角度 (°)','FontSize',9);
        ylabel('ADC 电压 (V)','FontSize',9);
        xlim([0,360]); xticks(0:45:360);
        legend('Location','northeast','FontSize',8,'Box','off','NumColumns',1);
        grid on; box on;
    end
end


% =========================================================
%  十六进制字符串 → uint8 数组
% =========================================================
function rawData = hexStringToBinary(textContent)
    cleanText = regexprep(textContent, '\s', '');
    if mod(length(cleanText), 2) ~= 0
        cleanText = cleanText(1:end-1);
    end
    dataLength = length(cleanText) / 2;
    rawData    = zeros(1, dataLength, 'uint8');
    for i = 1:dataLength
        rawData(i) = hex2dec(cleanText((i-1)*2+1 : i*2));
    end
    fprintf('十六进制转换完成，得到 %d 字节\n', dataLength);
end


% =========================================================
%  解析数据包
% =========================================================
function protocolData = parseVoltagePackets(rawData)
    START1 = hex2dec('5A');
    START2 = hex2dec('A5');
    END1   = hex2dec('0D');
    END2   = hex2dec('0A');
    PACKET_SIZE  = 10;
    TYPE_NOTHING = hex2dec('00');
    TYPE_MEASURE = hex2dec('01');
    TYPE_REFER   = hex2dec('02');
    INVALID_1    = uint8([0x00,0x00,0x00,0x00]);
    INVALID_2    = uint8([0xFF,0xFF,0xFF,0xFF]);

    protocolData = struct( ...
        'packets',          {{}}, ...
        'validPacketCount', 0,   ...
        'corruptedPackets', 0,   ...
        'invalidDataPackets',0,  ...
        'voltageValues',    [],  ...
        'packetTypes',      [],  ...
        'measureCount',     0,   ...
        'referCount',       0,   ...
        'nothingCount',     0,   ...
        'measureVoltages',  [],  ...
        'referVoltages',    []);

    i              = 1;
    packetCount    = 0;
    corruptedCount = 0;
    invalidCount   = 0;
    voltageValues  = [];
    packetTypes    = [];
    measureCount   = 0;
    referCount     = 0;
    nothingCount   = 0;
    measureVoltages = [];
    referVoltages   = [];

    while i <= length(rawData) - PACKET_SIZE + 1
        if rawData(i)   == START1 && rawData(i+1) == START2 && ...
           rawData(i+8) == END1   && rawData(i+9) == END2

            packet    = rawData(i : i+PACKET_SIZE-1);
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
                    measureCount = measureCount + 1;
                    typeStr = '测量光';
                    if chkOK && ~isInvalid
                        measureVoltages(end+1) = voltage; %#ok<AGROW>
                    end
                case TYPE_REFER
                    referCount = referCount + 1;
                    typeStr = '参考光';
                    if chkOK && ~isInvalid
                        referVoltages(end+1) = voltage; %#ok<AGROW>
                    end
                case TYPE_NOTHING
                    nothingCount = nothingCount + 1;
                    typeStr = '无类型';
                otherwise
                    typeStr = '未知类型';
            end

            protocolData.packets{packetCount} = struct( ...
                'rawData',           packet,    ...
                'startIndex',        i,         ...
                'dataType',          dataType,  ...
                'dataTypeStr',       typeStr,   ...
                'dataBytes',         dataBytes, ...
                'receivedChecksum',  chkRecv,   ...
                'calculatedChecksum',chkCalc,   ...
                'checksumValid',     chkOK,     ...
                'isInvalidData',     isInvalid, ...
                'voltageInt',        voltageInt,...
                'voltage',           voltage,   ...
                'dataValid',         chkOK && ~isInvalid);

            if chkOK && ~isInvalid
                voltageValues(end+1) = voltage;    %#ok<AGROW>
                packetTypes(end+1)   = dataType;   %#ok<AGROW>
            end
            if ~chkOK,    corruptedCount = corruptedCount + 1; end
            if isInvalid, invalidCount   = invalidCount   + 1; end

            i = i + PACKET_SIZE;
        else
            i = i + 1;
        end
    end

    protocolData.validPacketCount    = packetCount;
    protocolData.corruptedPackets    = corruptedCount;
    protocolData.invalidDataPackets  = invalidCount;
    protocolData.voltageValues       = voltageValues;
    protocolData.packetTypes         = packetTypes;
    protocolData.measureCount        = measureCount;
    protocolData.referCount          = referCount;
    protocolData.nothingCount        = nothingCount;
    protocolData.measureVoltages     = measureVoltages;
    protocolData.referVoltages       = referVoltages;
end


% =========================================================
%  统计量计算
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
%  测量光 / 参考光 物理角度对齐
% =========================================================
function protocolData = alignMeasureRefer(protocolData)
    MECH_ANGLE_DEG = 45;
    SEARCH_WINDOW  = 5;

    mV = protocolData.measureVoltages;
    rV = protocolData.referVoltages;

    % 默认值
    protocolData.alignOffset      = 0;
    protocolData.alignOffsetFixed = 0;
    protocolData.alignAngleDeg    = 0;
    protocolData.measureAligned   = mV;
    protocolData.referAligned     = rV;
    protocolData.alignValidLen    = min(length(mV), length(rV));
    protocolData.alignPearsonR    = NaN;
    protocolData.stepAngleDeg     = 0;
    protocolData.N                = 0;
    protocolData.fname            = '';
    protocolData.stem             = '';

    if isempty(mV) || isempty(rV), return; end

    N            = min(length(mV), length(rV));
    stepAngle    = 360.0 / N;
    offset_fixed = round(MECH_ANGLE_DEG / 360.0 * N);

    % 互相关搜索精确偏移
    m_seg = mV(1:N) - mean(mV(1:N));
    r_seg = rV(1:N) - mean(rV(1:N));
    [xc, lags] = xcorr(r_seg, m_seg, N-1, 'normalized');

    lo   = max(0,   offset_fixed - SEARCH_WINDOW);
    hi   = min(N-1, offset_fixed + SEARCH_WINDOW);
    mask = (lags >= lo) & (lags <= hi);

    if any(mask)
        [~, idx]        = max(xc(mask));
        valid_lags      = lags(mask);
        offset_refined  = valid_lags(idx);
    else
        offset_refined  = offset_fixed;
    end

    rV_shifted = circshift(rV(1:N), -offset_refined);
    valid_len  = N - abs(offset_refined);
    m_aligned  = mV(1:valid_len);
    r_aligned  = rV_shifted(1:valid_len);
    pearson_r  = corr(m_aligned(:), r_aligned(:));

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
%  控制台打印结果
% =========================================================
function displayVoltageResults(protocolData)
    fprintf('  有效包: %d  校验错: %d  无效值: %d\n', ...
        protocolData.validPacketCount, ...
        protocolData.corruptedPackets, ...
        protocolData.invalidDataPackets);
    fprintf('  测量光: %d  参考光: %d  无类型: %d\n', ...
        protocolData.measureCount, ...
        protocolData.referCount, ...
        protocolData.nothingCount);
    fprintf('  对齐偏移: %d 点 (%.2f°)  Pearson r = %.4f\n\n', ...
        protocolData.alignOffset, ...
        protocolData.alignAngleDeg, ...
        protocolData.alignPearsonR);
end


% =========================================================
%  保存数据到 txt 文件
% =========================================================
function saveVoltageDataToFiles(protocolData, measureFilePath, ...
                                referFilePath, alignedFilePath, humidityData)
    % 测量光
    if ~isempty(protocolData.measureVoltages)
        fid = fopen(measureFilePath, 'w');
        if fid ~= -1
            fprintf(fid, '# Humidity: %s\n# Count: %d\n#\n', ...
                humidityData, length(protocolData.measureVoltages));
            fprintf(fid, '%.6f\n', protocolData.measureVoltages);
            fclose(fid);
        end
    end

    % 参考光
    if ~isempty(protocolData.referVoltages)
        fid = fopen(referFilePath, 'w');
        if fid ~= -1
            fprintf(fid, '# Humidity: %s\n# Count: %d\n#\n', ...
                humidityData, length(protocolData.referVoltages));
            fprintf(fid, '%.6f\n', protocolData.referVoltages);
            fclose(fid);
        end
    end

    % 对齐后双列
    if ~isempty(protocolData.measureAligned) && ~isempty(protocolData.referAligned)
        fid = fopen(alignedFilePath, 'w');
        if fid ~= -1
            fprintf(fid, '# Humidity: %s\n# Offset: %d pts (%.2f deg)\n# Pearson r: %.4f\n#\n', ...
                humidityData, protocolData.alignOffset, ...
                protocolData.alignAngleDeg, protocolData.alignPearsonR);
            for i = 1:protocolData.alignValidLen
                fprintf(fid, '%.6f\t%.6f\n', ...
                    protocolData.measureAligned(i), ...
                    protocolData.referAligned(i));
            end
            fclose(fid);
        end
    end

    fprintf('  已保存：%s\n', measureFilePath);
end
