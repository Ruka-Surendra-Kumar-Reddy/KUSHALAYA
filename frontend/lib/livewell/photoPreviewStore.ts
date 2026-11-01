const DB_NAME = "safehome_hs_photo_previews_v1";
const STORE = "previews";

function previewKey(assessmentId: string, photoId: string): string {
  return `${assessmentId}/${photoId}`;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, 1);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"));
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
  });
}

export async function savePhotoPreview(
  assessmentId: string,
  photoId: string,
  blob: Blob,
): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("IndexedDB write failed"));
      tx.objectStore(STORE).put(blob, previewKey(assessmentId, photoId));
    });
  } finally {
    db.close();
  }
}

export async function getPhotoPreviewBlob(
  assessmentId: string,
  photoId: string,
): Promise<Blob | null> {
  try {
    const db = await openDb();
    try {
      return await new Promise<Blob | null>((resolve, reject) => {
        const tx = db.transaction(STORE, "readonly");
        tx.onerror = () => reject(tx.error ?? new Error("IndexedDB read failed"));
        const req = tx.objectStore(STORE).get(previewKey(assessmentId, photoId));
        req.onsuccess = () => resolve((req.result as Blob | undefined) ?? null);
        req.onerror = () => reject(req.error ?? new Error("IndexedDB read failed"));
      });
    } finally {
      db.close();
    }
  } catch {
    return null;
  }
}

export async function deletePhotoPreview(assessmentId: string, photoId: string): Promise<void> {
  try {
    const db = await openDb();
    try {
      await new Promise<void>((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error ?? new Error("IndexedDB delete failed"));
        tx.objectStore(STORE).delete(previewKey(assessmentId, photoId));
      });
    } finally {
      db.close();
    }
  } catch {
    /* ignore */
  }
}

export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const res = await fetch(dataUrl);
  return res.blob();
}

export async function savePhotoPreviewFromDataUrl(
  assessmentId: string,
  photoId: string,
  dataUrl: string,
): Promise<void> {
  const blob = await dataUrlToBlob(dataUrl);
  await savePhotoPreview(assessmentId, photoId, blob);
}
