document.addEventListener('DOMContentLoaded', function () {
    // vWorld API Key
    const vworldKey = "98574D34-73D4-351E-B16C-27513BD72D8D";

    // Base Layer (vWorld)
    const baseLayer = new ol.layer.Tile({
        source: new ol.source.XYZ({
            url: `https://api.vworld.kr/req/wmts/1.0.0/${vworldKey}/Base/{z}/{y}/{x}.png`
        })
    });

    // View (Center on Korea)
    const view = new ol.View({
        center: ol.proj.fromLonLat([127.5, 36.5]),
        zoom: 7
    });

    // Map
    const map = new ol.Map({
        target: 'map',
        layers: [baseLayer],
        view: view
    });

    // Popup Overlay
    const container = document.getElementById('popup');
    const content = document.getElementById('popup-content');
    const closer = document.getElementById('popup-closer');

    const overlay = new ol.Overlay({
        element: container,
        autoPan: true,
        autoPanAnimation: {
            duration: 250
        }
    });
    map.addOverlay(overlay);

    closer.onclick = function () {
        overlay.setPosition(undefined);
        closer.blur();
        return false;
    };

    // Load Basin GeoJSON
    const basinSource = new ol.source.Vector({
        url: '/static/WKMSBSN.geojson',
        format: new ol.format.GeoJSON()
    });

    const basinLayer = new ol.layer.Vector({
        source: basinSource,
        style: new ol.style.Style({
            stroke: new ol.style.Stroke({
                color: 'rgba(0, 0, 255, 0.6)',
                width: 2
            }),
            fill: new ol.style.Fill({
                color: 'rgba(0, 0, 255, 0.1)'
            })
        })
    });
    map.addLayer(basinLayer);

    // Fit view to basin when loaded
    basinSource.once('change', function () {
        if (basinSource.getState() === 'ready') {
            const extent = basinSource.getExtent();
            if (!ol.extent.isEmpty(extent)) {
                view.fit(extent, { padding: [50, 50, 50, 50] });
            }
        }
    });

    // Candidate Layer
    const candidateSource = new ol.source.Vector({
        url: '/static/candidates.geojson',
        format: new ol.format.GeoJSON()
    });

    const candidateLayer = new ol.layer.Vector({
        source: candidateSource,
        style: new ol.style.Style({
            image: new ol.style.Circle({
                radius: 6,
                fill: new ol.style.Fill({ color: 'red' }),
                stroke: new ol.style.Stroke({ color: 'white', width: 2 })
            })
        })
    });
    map.addLayer(candidateLayer);

    // Click Event (Terrain Query)
    map.on('singleclick', function (evt) {
        // If we clicked on a feature (candidate), let the select interaction handle it
        if (map.hasFeatureAtPixel(evt.pixel, { layerFilter: l => l === candidateLayer })) {
            return;
        }

        const coordinate = evt.coordinate;
        const lonLat = ol.proj.toLonLat(coordinate);

        // Update Info Panel
        document.getElementById('info-content').innerHTML = `
            <p><strong>좌표:</strong> ${lonLat[0].toFixed(5)}, ${lonLat[1].toFixed(5)}</p>
            <p>데이터 조회 중...</p>
        `;

        // Query Backend
        fetch(`/api/query?x=${lonLat[0]}&y=${lonLat[1]}`)
            .then(response => response.json())
            .then(data => {
                let html = `<p><strong>좌표:</strong> ${lonLat[0].toFixed(5)}, ${lonLat[1].toFixed(5)}</p>`;
                if (data.error) {
                    html += `<p style="color:red;">Error: ${data.error}</p>`;
                } else {
                    html += `
                        <p><strong>고도:</strong> ${data.elevation.toFixed(2)} m</p>
                        <p><strong>경사:</strong> ${data.slope}</p>
                        <p><strong>TWI:</strong> ${data.twi}</p>
                    `;
                }
                document.getElementById('info-content').innerHTML = html;

                // Show Popup
                content.innerHTML = html;
                overlay.setPosition(coordinate);
            })
            .catch(err => {
                console.error(err);
                document.getElementById('info-content').innerHTML = "Error fetching data.";
            });
    });

    // Candidate Selection (Popup with Reason & Download)
    const selectInteraction = new ol.interaction.Select({
        layers: [candidateLayer],
        style: null // Use existing style
    });
    map.addInteraction(selectInteraction);

    selectInteraction.on('select', function (e) {
        if (e.selected.length > 0) {
            const feature = e.selected[0];
            const props = feature.getProperties();
            const geometry = feature.getGeometry();
            const coord = geometry.getCoordinates();

            const reason = props.reason || "정보 없음";
            const score = props.score ? props.score.toFixed(1) : "N/A";

            const html = `
                <div style="min-width: 200px;">
                    <h4>후보지 상세 정보</h4>
                    <p><strong>점수:</strong> ${score}점</p>
                    <p><strong>선정 이유:</strong><br>${reason}</p>
                    <hr>
                    <button onclick="downloadReport('${score}', '${reason.replace(/'/g, "\\'")}')" style="cursor:pointer; padding:5px 10px; background:#007bff; color:white; border:none; border-radius:4px;">
                        보고서 저장 (.txt)
                    </button>
                </div>
            `;

            content.innerHTML = html;
            overlay.setPosition(coord);
        }
    });

    // Controls
    document.getElementById('toggle-basin').addEventListener('click', function () {
        basinLayer.setVisible(!basinLayer.getVisible());
    });

    document.getElementById('toggle-candidates').addEventListener('click', function () {
        candidateLayer.setVisible(!candidateLayer.getVisible());
    });

    // --- AOI Analysis Feature ---
    const aoiSource = new ol.source.Vector();
    const aoiLayer = new ol.layer.Vector({
        source: aoiSource,
        style: new ol.style.Style({
            fill: new ol.style.Fill({
                color: 'rgba(255, 255, 255, 0.2)'
            }),
            stroke: new ol.style.Stroke({
                color: '#ffcc33',
                width: 2
            }),
            image: new ol.style.Circle({
                radius: 7,
                fill: new ol.style.Fill({
                    color: '#ffcc33'
                })
            })
        })
    });
    map.addLayer(aoiLayer);

    let draw; // global so we can remove it later
    const drawButton = document.getElementById('draw-aoi');
    const analyzeButton = document.getElementById('run-aoi-analysis');

    drawButton.addEventListener('click', function () {
        // Clear previous AOI
        aoiSource.clear();
        analyzeButton.disabled = true;

        // Add interaction
        draw = new ol.interaction.Draw({
            source: aoiSource,
            type: 'Polygon'
        });
        map.addInteraction(draw);

        draw.on('drawend', function () {
            map.removeInteraction(draw);
            analyzeButton.disabled = false;
        });
    });

    analyzeButton.addEventListener('click', function () {
        const features = aoiSource.getFeatures();
        if (features.length === 0) return;

        const feature = features[0];
        const geometry = feature.getGeometry();

        const format = new ol.format.GeoJSON();
        const geojson = format.writeGeometryObject(geometry, {
            dataProjection: 'EPSG:4326',
            featureProjection: 'EPSG:3857'
        });

        analyzeButton.textContent = "분석 중...";
        analyzeButton.disabled = true;

        fetch('/api/analyze_aoi', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(geojson)
        })
            .then(response => response.json())
            .then(data => {
                analyzeButton.textContent = "영역 분석 실행";
                analyzeButton.disabled = false;

                if (data.error) {
                    alert("Error: " + data.error);
                    return;
                }

                if (data.message) {
                    alert(data.message);
                }

                const newFeatures = format.readFeatures(data, {
                    dataProjection: 'EPSG:4326',
                    featureProjection: 'EPSG:3857'
                });

                candidateSource.addFeatures(newFeatures);
                alert(`분석 완료! ${newFeatures.length}개의 후보지를 찾았습니다.`);
            })
            .catch(err => {
                console.error(err);
                analyzeButton.textContent = "영역 분석 실행";
                analyzeButton.disabled = false;
                alert("분석 요청 실패");
            });
    });

    // Global function for download
    window.downloadReport = function (score, reason) {
        const text = `[지하수저류댐 후보지 분석 보고서]\n\n` +
            `종합 점수: ${score}점\n` +
            `선정 이유:\n${reason}\n\n` +
            `분석 일시: ${new Date().toLocaleString()}\n` +
            `생성: NGII 자동평가 모델`;

        const blob = new Blob([text], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `candidate_report_${score}.txt`;
        a.click();
        window.URL.revokeObjectURL(url);
    };
});
