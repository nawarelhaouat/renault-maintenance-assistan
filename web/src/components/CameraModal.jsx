import { useEffect, useRef, useState } from "react";
import { Camera, X } from "lucide-react";

export default function CameraModal({ onCapture, onClose }) {
  const video = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let stream;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        video.current.srcObject = s;
      })
      .catch(() => setError("Caméra inaccessible. Autorise l'accès ou importe une image."));
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const snap = () => {
    const v = video.current;
    if (!v?.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d").drawImage(v, 0, 0);
    canvas.toBlob((b) => b && onCapture(new File([b], "photo.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92);
  };

  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        {error ? <div className="error">{error}</div> : <video ref={video} autoPlay playsInline muted />}
        <div className="row spread">
          <button className="btn" onClick={onClose}><X size={15} />Fermer</button>
          <button className="btn primary" onClick={snap} disabled={!!error}><Camera size={15} />Capturer</button>
        </div>
      </div>
    </div>
  );
}