'use client';

import React, { useRef } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { motion } from 'framer-motion-3d';

/**
 * Epic 16: Supply Chain Digital Twin (Google Earth Engine Integration)
 * A WebGL 3D Globe component illustrating the real-time physical state of the 
 * Alti.Analytics Sovereign Omniverse.
 */

function EarthMesh() {
    const earthRef = useRef<THREE.Mesh>(null);

    // Rotate the earth slowly
    useFrame(() => {
        if (earthRef.current) {
            earthRef.current.rotation.y += 0.001;
        }
    });

    return (
        <motion.mesh
            ref={earthRef}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ duration: 1.5, ease: "easeOut" }}
        >
            <sphereGeometry args={[2, 64, 64]} />
            {/* A stylized dark-mode wireframe/glass aesthetic for the globe */}
            <meshStandardMaterial
                color="#0ea5e9"
                wireframe={true}
                transparent={true}
                opacity={0.3}
                roughness={0.1}
                metalness={0.8}
            />
            {/* Inner core to give it depth */}
            <mesh>
                <sphereGeometry args={[1.98, 32, 32]} />
                <meshBasicMaterial color="#020617" />
            </mesh>

            {/* Epic 16: Anomaly Visualization (Typhoon Simulation) */}
            <AnomalyMarker lat={12.5} lon={130.0} color="#ef4444" label="Category 4 Typhoon" />

            {/* Asset Visualization (Maersk Vessel) */}
            <AssetMarker lat={10.0} lon={125.0} color="#10b981" label="Vessel 8X-Maersk" />
        </motion.mesh>
    );
}

// Helper to convert Lat/Lon to 3D Cartesian Coordinates on the sphere
function latLongToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);

    const x = -(radius * Math.sin(phi) * Math.cos(theta));
    const z = (radius * Math.sin(phi) * Math.sin(theta));
    const y = (radius * Math.cos(phi));

    return new THREE.Vector3(x, y, z);
}

function AnomalyMarker({ lat, lon, color, label }: { lat: number, lon: number, color: string, label: string }) {
    const position = latLongToVector3(lat, lon, 2.05);
    return (
        <mesh position={position}>
            <sphereGeometry args={[0.08, 16, 16]} />
            <meshBasicMaterial color={color} />
            {/* In a real app, use Drei's <Html> for labels */}
        </mesh>
    );
}

function AssetMarker({ lat, lon, color, label }: { lat: number, lon: number, color: string, label: string }) {
    const position = latLongToVector3(lat, lon, 2.05);
    return (
        <mesh position={position}>
            <boxGeometry args={[0.05, 0.05, 0.05]} />
            <meshBasicMaterial color={color} />
        </mesh>
    );
}

export default function DigitalTwinGlobe() {
    return (
        <div className="w-full h-full min-h-[400px] relative rounded-xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-md">
            {/* Canvas establishing the WebGL Context */}
            <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} intensity={1.5} />

                {/* Background stars for deep-space/cyberpunk aesthetic */}
                <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />

                <EarthMesh />

                <OrbitControls enableZoom={false} autoRotate={false} />
            </Canvas>

            <div className="absolute bottom-4 left-4 p-4 rounded-lg bg-black/60 border border-white/5 backdrop-blur-sm">
                <h3 className="text-white font-semibold text-sm">Alti.Analytics Satellite Feed</h3>
                <p className="text-gray-400 text-xs mt-1">Status: Tracking 1.2M Physical Assets</p>
                <div className="mt-2 flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                    <span className="text-red-400 text-xs font-mono">CRITICAL: Severe Weather Detected in APAC</span>
                </div>
            </div>
        </div>
    );
}
