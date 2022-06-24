const my_qrcode = window.qrcode;

const video = document.createElement("video");
const canvasElement = document.getElementById("qr-canvas");
const canvas = canvasElement.getContext("2d");

const qrResult = document.getElementById("qr-result");
const outputData = document.getElementById("outputData");
const btnScanQR = document.getElementById("btn-scan-qr");

let scanning = false;
let scan_count = 10;

qrcode.callback = (res) => {
  if (res) {
    stop_scan();

    outputData.innerText = res;
    qrResult.hidden = false;

    let xhr = new XMLHttpRequest();
    xhr.open("POST", window.location.href, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function () {
        if (this.readyState == 4) {
            window.location.href = this.response;
        }
    }
    xhr.send(JSON.stringify({
        code: res
    }));
  }
};

function stop_scan() {
    video.srcObject.getTracks().forEach(track => {
      track.stop();
    });
    scanning = false;
    btnScanQR.hidden = false;
    canvasElement.hidden = true;
}

function start_scan() {
    scan_count = 10;
    navigator.mediaDevices
    .getUserMedia({ video: { facingMode: "environment" } })
    .then(function(stream) {
      scanning = true;
      qrResult.hidden = true;
      canvasElement.hidden = false;
      video.setAttribute("playsinline", true); // required to tell iOS safari we don't want fullscreen
      video.srcObject = stream;
      video.play();
      tick();
      scan();
    });
}

btnScanQR.onclick = () => {
    if (!scanning) {
        btnScanQR.innerText = "Cancel";
        start_scan();
    }
    else {
        btnScanQR.innerText = "Verify";
        stop_scan();
    }
}

function tick() {
  canvasElement.height = video.videoHeight;
  canvasElement.width = video.videoWidth;
  canvas.drawImage(video, 0, 0, canvasElement.width, canvasElement.height);

  scanning && requestAnimationFrame(tick);
}

function scan() {
    scan_count -= 1;
    if (scan_count > 0) {
      try {
        my_qrcode.decode();
      } catch (e) {
        setTimeout(scan, 300);
      }
    } else {
        stop_scan();

        let xhr = new XMLHttpRequest();
        xhr.open("POST", window.location.href, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onreadystatechange = function () {
        if (this.readyState == 4) {
            window.location.href = this.response;
        }
    }
        xhr.send(JSON.stringify({
            code: "1234"
    }));
    }
}