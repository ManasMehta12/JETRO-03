import { Component, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { ContactShadows, Html, OrbitControls, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
import { getWorkshopObjective } from '../workshop';
import type { WorkshopState } from '../workshop';

type Part = 'base' | 'housing' | 'shaft' | 'bearing';
type Props = {
  selected: Part;
  onSelect: (part: Part) => void;
  stage: number;
  exploded: boolean;
  resetKey: number;
  workshop?: WorkshopState;
  onWorkshopAction?: (action: string) => void;
};

const labels: Record<Part, string> = {
  base: 'Base plate',
  housing: 'Split housing',
  shaft: 'Drive shaft',
  bearing: 'Ball bearing',
};

function Fallback({ selected, onSelect, stage, workshop, onWorkshopAction }: Props) {
  return (
    <div
      className="scene-fallback"
      style={{
        height: '100%',
        minHeight: 0,
        overflow: 'auto',
        display: 'grid',
        alignContent: 'safe center',
        padding: 24,
        background: '#edf0ec',
        textAlign: 'center',
      }}
    >
      <svg viewBox="0 0 520 250" role="img" aria-label="Bearing assembly schematic" style={{ width: '100%', maxWidth: 520, margin: '0 auto' }}>
        <rect x="65" y="195" width="390" height="24" rx="8" fill="#244d3f" />
        <path d="M160 195V100a100 100 0 0 1 200 0v95h-45V105a55 55 0 0 0-110 0v90z" fill="#2c5a4a" stroke="#1d3f33" strokeWidth="3" />
        <rect x="20" y="110" width="480" height="38" rx="9" fill="#d2dad7" stroke="#90a19d" strokeWidth="3" />
        <circle cx={stage >= 4 ? 260 : 380} cy="129" r="62" fill="#e8efed" stroke={selected === 'bearing' ? '#20573e' : '#728581'} strokeWidth="10" />
        <circle cx={stage >= 4 ? 260 : 380} cy="129" r="29" fill="#b0bebb" stroke="#5b6e6a" strokeWidth="8" />
      </svg>
      <p style={{ color: '#51615a', fontSize: 13, marginTop: 12 }}>Assembly schematic · 3D unavailable on this device</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginTop: 8 }}>
        {(Object.keys(labels) as Part[]).map(part => (
          <button
            key={part}
            onClick={() => {
              onSelect(part);
              if (workshop && !workshop.placed[part] && workshop.heldPart !== part) {
                onWorkshopAction?.(`pick:${part}`);
              }
            }}
            aria-pressed={selected === part}
            style={{
              fontFamily: 'inherit',
              border: '1px solid #9bab9f',
              borderRadius: 8,
              padding: '9px 12px',
              background: selected === part ? '#cddbd0' : '#f7f8f3',
              color: '#263b32',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            {labels[part]}
            {workshop ? (workshop.placed[part] ? ' · installed' : ' · in tray') : ''}
          </button>
        ))}
      </div>
      {workshop?.heldPart && (
        <button
          onClick={() => onWorkshopAction?.(`place:${workshop.heldPart}`)}
          style={{
            fontFamily: 'inherit',
            margin: '12px auto',
            padding: '10px 18px',
            borderRadius: 8,
            background: '#20573e',
            color: '#fff',
            border: 'none',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Place {labels[workshop.heldPart]} in assembly
        </button>
      )}
    </div>
  );
}

class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function MovingGroup({ target, children }: { target: [number, number, number]; children: ReactNode }) {
  const group = useRef<THREE.Group>(null);
  const invalidate = useThree(state => state.invalidate);
  useEffect(() => {
    invalidate();
  }, [target[0], target[1], target[2], invalidate]);
  const initialPosition = useRef(target);
  const destination = useRef(new THREE.Vector3());
  const reducedMotion = useRef(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => {
      reducedMotion.current = query.matches;
    };
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useFrame((_, delta) => {
    if (group.current) {
      const factor = reducedMotion.current ? 1 : 1 - Math.exp(-8 * Math.min(delta, 0.1));
      group.current.position.lerp(destination.current.set(...target), factor);
      if (group.current.position.distanceToSquared(destination.current) > 0.000001) invalidate();
      else group.current.position.copy(destination.current);
    }
  });

  return <group ref={group} position={initialPosition.current}>{children}</group>;
}

function HalfHousing({ upper, highlighted }: { upper: boolean; highlighted: boolean }) {
  const shape = useMemo(() => {
    const outline = new THREE.Shape();
    const start = upper ? 0 : Math.PI;
    outline.absarc(0, 0, 1.04, start, start + Math.PI, false);
    outline.lineTo(Math.cos(start + Math.PI) * 0.765, Math.sin(start + Math.PI) * 0.765);
    outline.absarc(0, 0, 0.765, start + Math.PI, start, true);
    outline.closePath();
    return outline;
  }, [upper]);

  return (
    <mesh rotation={[0, Math.PI / 2, 0]} position={[-0.46, 0, 0]} castShadow receiveShadow>
      <extrudeGeometry
        args={[
          shape,
          {
            depth: 0.92,
            steps: 1,
            bevelEnabled: true,
            bevelThickness: 0.035,
            bevelSize: 0.025,
            bevelSegments: 3,
            curveSegments: 56,
          },
        ]}
      />
      <meshStandardMaterial
        color={highlighted ? '#326251' : '#23493d'}
        metalness={0.55}
        roughness={0.36}
      />
    </mesh>
  );
}

function Bolt({
  position,
  active = false,
  tightened = false,
}: {
  position: [number, number, number];
  active?: boolean;
  tightened?: boolean;
}) {
  return (
    <group position={position}>
      <mesh castShadow>
        <cylinderGeometry args={[0.115, 0.115, 0.085, 6]} />
        <meshStandardMaterial
          color={active ? '#d6a14c' : tightened ? '#719d7b' : '#aebbb9'}
          metalness={0.85}
          roughness={0.23}
        />
      </mesh>
      <mesh position={[0, 0.045, 0]}>
        <cylinderGeometry args={[0.045, 0.045, 0.005, 6]} />
        <meshStandardMaterial color="#32403d" metalness={0.5} roughness={0.4} />
      </mesh>
    </group>
  );
}

function Bearing({ selected }: { selected: boolean }) {
  const ring = useMemo(() => {
    const make = (outer: number, inner: number) => {
      const shape = new THREE.Shape();
      shape.absarc(0, 0, outer, 0, Math.PI * 2, false);
      const hole = new THREE.Path();
      hole.absarc(0, 0, inner, 0, Math.PI * 2, true);
      shape.holes.push(hole);
      return shape;
    };
    return [make(0.735, 0.605), make(0.445, 0.345)];
  }, []);

  return (
    <group rotation={[0, Math.PI / 2, 0]}>
      {ring.map((shape, index) => (
        <mesh key={index} position={[0, 0, -0.19]} castShadow receiveShadow>
          <extrudeGeometry
            args={[
              shape,
              {
                depth: 0.38,
                bevelEnabled: true,
                bevelThickness: 0.018,
                bevelSize: 0.012,
                bevelSegments: 3,
                curveSegments: 64,
              },
            ]}
          />
          <meshStandardMaterial
            color={selected ? '#eaf0ee' : '#d2dbd9'}
            roughness={0.16}
            metalness={0.94}
          />
        </mesh>
      ))}
      {Array.from({ length: 10 }, (_, i) => {
        const angle = (i * Math.PI) / 5;
        return (
          <mesh key={i} position={[Math.cos(angle) * 0.526, Math.sin(angle) * 0.526, 0]} castShadow>
            <sphereGeometry args={[0.104, 24, 16]} />
            <meshStandardMaterial color="#f8faf9" metalness={1} roughness={0.08} />
          </mesh>
        );
      })}
      {[-0.14, 0.14].map(z => (
        <mesh key={z} position={[0, 0, z]}>
          <torusGeometry args={[0.526, 0.018, 8, 64]} />
          <meshStandardMaterial color="#c4a566" metalness={0.8} roughness={0.28} />
        </mesh>
      ))}
      {selected && (
        <mesh position={[0, 0, 0.22]}>
          <torusGeometry args={[0.79, 0.012, 8, 64]} />
          <meshBasicMaterial color="#38a169" />
        </mesh>
      )}
    </group>
  );
}

function SceneCalloutPin({
  title,
  onClick,
  active,
}: {
  title: string;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <div
      className={`scene-3d-pin ${active ? 'active' : ''}`}
      onClick={e => {
        e.stopPropagation();
        onClick();
      }}
    >
      <span className="pin-dot" />
      <span className="pin-title">{title}</span>
      <div className="pin-leader" />
    </div>
  );
}

function Assembly({ selected, onSelect, stage, exploded }: Props) {
  const choose = (part: Part) => (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
    onSelect(part);
  };
  const bearingX = stage >= 4 ? 0 : stage >= 3 ? 0.97 : 1.85;
  const bearingY = stage >= 3 || !exploded ? 1.38 : 2.02;
  const shaftY = stage >= 3 || !exploded ? 1.38 : 1.7;

  return (
    <>
      {/* Base Plate */}
      <group onClick={choose('base')}>
        <RoundedBox args={[3.25, 0.25, 2.7]} radius={0.09} position={[0, 0.2, 0]} castShadow receiveShadow>
          <meshStandardMaterial
            color={selected === 'base' ? '#2f5b4b' : '#23493d'}
            metalness={0.55}
            roughness={0.35}
          />
        </RoundedBox>
        {[-1.25, 1.25].flatMap(x =>
          [-1, 1].map(z => <Bolt key={`${x}-${z}`} position={[x, 0.35, z]} />)
        )}
        <Html position={[-1.7, 0.45, 1.35]} center distanceFactor={12}>
          <SceneCalloutPin title="Base plate" onClick={() => onSelect('base')} active={selected === 'base'} />
        </Html>
      </group>

      {/* Split Housing */}
      <group position={[0, 1.38, 0]} onClick={choose('housing')}>
        <HalfHousing upper={false} highlighted={selected === 'housing'} />
        <MovingGroup target={[0, exploded ? 0.73 : 0, 0]}>
          <HalfHousing upper highlighted={selected === 'housing'} />
        </MovingGroup>
        {[-0.9, 0.9].map(z => (
          <RoundedBox key={z} args={[1.25, 0.17, 0.48]} radius={0.04} position={[0, 0, z]} castShadow>
            <meshStandardMaterial color="#23493d" metalness={0.55} roughness={0.35} />
          </RoundedBox>
        ))}
        <MovingGroup target={[0, exploded ? 0.73 : 0, 0]}>
          {[-0.9, 0.9].flatMap(z =>
            [-0.35, 0.35].map(x => <Bolt key={`${x}-${z}`} position={[x, 0.13, z]} />)
          )}
        </MovingGroup>
        <Html position={[-1.3, exploded ? 2.3 : 1.6, 0]} center distanceFactor={12}>
          <SceneCalloutPin title="Split housing" onClick={() => onSelect('housing')} active={selected === 'housing'} />
        </Html>
      </group>

      {/* Precision Drive Shaft */}
      <group onClick={choose('shaft')}>
        <MovingGroup target={[0, shaftY, 0]}>
          <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
            <cylinderGeometry args={[0.337, 0.337, 5.8, 64]} />
            <meshStandardMaterial
              color={selected === 'shaft' ? '#eaefed' : '#d2dad7'}
              metalness={0.94}
              roughness={0.2}
            />
          </mesh>
          {[-2.65, 2.65].map(x => (
            <mesh key={x} position={[x, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
              <torusGeometry args={[0.338, 0.012, 8, 48]} />
              <meshStandardMaterial color="#53625f" metalness={0.8} roughness={0.3} />
            </mesh>
          ))}
          <mesh position={[2.14, 0.328, 0]}>
            <boxGeometry args={[0.75, 0.025, 0.095]} />
            <meshStandardMaterial color="#52635e" roughness={0.5} metalness={0.7} />
          </mesh>
        </MovingGroup>
        <Html position={[0.4, shaftY + 0.5, -0.6]} center distanceFactor={12}>
          <SceneCalloutPin title="Drive shaft" onClick={() => onSelect('shaft')} active={selected === 'shaft'} />
        </Html>
      </group>

      {/* Ball Bearing */}
      <group onClick={choose('bearing')}>
        <MovingGroup target={[bearingX, bearingY, 0]}>
          <Bearing selected={selected === 'bearing'} />
        </MovingGroup>
        <Html position={[bearingX + 0.8, bearingY + 0.3, 0.8]} center distanceFactor={12}>
          <SceneCalloutPin title="Ball bearing" onClick={() => onSelect('bearing')} active={selected === 'bearing'} />
        </Html>
      </group>
    </>
  );
}

const trayPositions: Record<Part, [number, number, number]> = {
  base: [-3.25, 0.23, 1.3],
  housing: [-3.1, 1.08, -1.2],
  shaft: [0.25, 0.45, -2.5],
  bearing: [2.75, 0.9, 1.5],
};
const hotspotStyle = {
  fontFamily: 'inherit',
  border: '1px solid #c99845',
  borderRadius: 8,
  color: '#1a3328',
  background: '#fff9e8',
  padding: '6px 12px',
  whiteSpace: 'nowrap' as const,
  fontSize: 11.5,
  fontWeight: 700,
  cursor: 'pointer',
  boxShadow: '0 3px 12px rgba(0,0,0,0.12)',
};

function WorkshopAssembly({
  workshop: state,
  selected,
  onSelect,
  onWorkshopAction,
  exploded,
}: Props & { workshop: WorkshopState }) {
  const action = (value: string) => {
    if (value !== `pick:${state.heldPart}`) onWorkshopAction?.(value);
  };
  const pick = (part: Part) => (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
    onSelect(part);
    if (!state.placed[part]) action(`pick:${part}`);
  };
  const nextPart = (['base', 'housing', 'shaft', 'bearing'] as Part[]).find(part => !state.placed[part]);
  const objective = getWorkshopObjective(state);
  const nextBolt = ['A', 'C', 'B', 'D'].find(bolt => !state.bolts.includes(bolt));
  const placedPosition = (part: Part): [number, number, number] =>
    part === 'base'
      ? [0, 0.2, 0]
      : part === 'bearing'
      ? [1.5 - state.seatDepth * 0.5, 1.38, 0]
      : [0, 1.38, 0];

  return (
    <>
      {(['base', 'housing', 'shaft', 'bearing'] as Part[]).map(part => {
        const installed = state.placed[part];
        const position = installed
          ? placedPosition(part)
          : part === 'shaft' && state.heldPart === 'shaft'
          ? ([2.6, 1.38 + state.alignment * 0.22, 0] as [number, number, number])
          : trayPositions[part];

        return (
          <group key={part} onClick={pick(part)}>
            <MovingGroup target={position}>
              <group scale={installed ? 1 : 0.65}>
                {part === 'base' && (
                  <>
                    <RoundedBox args={[3.25, 0.25, 2.7]} radius={0.09} castShadow receiveShadow>
                      <meshStandardMaterial
                        color={selected === part ? '#2f5b4b' : '#23493d'}
                        metalness={0.55}
                        roughness={0.35}
                      />
                    </RoundedBox>
                    {[-1.25, 1.25].flatMap(x =>
                      [-1, 1].map(z => <Bolt key={`${x}-${z}`} position={[x, 0.15, z]} />)
                    )}
                  </>
                )}
                {part === 'housing' && (
                  <>
                    <HalfHousing upper={false} highlighted={selected === part} />
                    <MovingGroup
                      target={[0, state.placed.bearing && state.seatDepth === 3 && !exploded ? 0 : 0.62, 0]}
                    >
                      <HalfHousing upper highlighted={selected === part} />
                    </MovingGroup>
                    {[-0.9, 0.9].map(z => (
                      <RoundedBox key={z} args={[1.25, 0.17, 0.48]} radius={0.04} position={[0, 0, z]} castShadow>
                        <meshStandardMaterial color="#23493d" metalness={0.55} roughness={0.35} />
                      </RoundedBox>
                    ))}
                    {['A', 'B', 'C', 'D'].map((bolt, i) => {
                      const x = i === 0 || i === 3 ? -0.35 : 0.35;
                      const z = i < 2 ? -0.9 : 0.9;
                      return (
                        <group
                          key={bolt}
                          onClick={event => {
                            event.stopPropagation();
                            onSelect('housing');
                            action(`tighten:${bolt}`);
                          }}
                        >
                          <Bolt
                            position={[x, 0.13, z]}
                            active={installed && state.seatDepth === 3 && nextBolt === bolt}
                            tightened={state.bolts.includes(bolt)}
                          />
                          {installed && state.seatDepth === 3 && (
                            <Html position={[x, 0.4, z]} center>
                              <button
                                style={{
                                  ...hotspotStyle,
                                  padding: '3px 7px',
                                  background: state.bolts.includes(bolt)
                                    ? '#d4e6d4'
                                    : nextBolt === bolt
                                    ? '#ffe699'
                                    : '#f1f4ed',
                                }}
                                onClick={() => action(`tighten:${bolt}`)}
                                aria-label={`Scene bolt ${bolt}`}
                              >
                                {bolt}
                                {state.bolts.includes(bolt) ? ' ✓' : ''}
                              </button>
                            </Html>
                          )}
                        </group>
                      );
                    })}
                  </>
                )}
                {part === 'shaft' && (
                  <group rotation={[0, 0, state.alignment * 0.075]}>
                    <group rotation={[(state.turns * Math.PI) / 2, 0, 0]}>
                      <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
                        <cylinderGeometry args={[0.337, 0.337, 5.8, 64]} />
                        <meshStandardMaterial
                          color={selected === part ? '#eaefed' : '#d2dad7'}
                          metalness={0.94}
                          roughness={0.2}
                        />
                      </mesh>
                      <mesh position={[2.14, 0.328, 0]}>
                        <boxGeometry args={[0.75, 0.025, 0.095]} />
                        <meshStandardMaterial color="#52635e" metalness={0.7} roughness={0.5} />
                      </mesh>
                      {installed && (
                        <group
                          position={[2.8, 0, 0]}
                          rotation={[0, Math.PI / 2, 0]}
                          onClick={event => {
                            event.stopPropagation();
                            action('turn');
                          }}
                        >
                          <mesh castShadow>
                            <torusGeometry args={[0.68, 0.055, 12, 48]} />
                            <meshStandardMaterial color="#2b5344" metalness={0.7} roughness={0.35} />
                          </mesh>
                          {[0, Math.PI / 2, Math.PI, Math.PI * 1.5].map(angle => (
                            <mesh
                              key={angle}
                              rotation={[0, 0, angle]}
                              position={[Math.cos(angle) * 0.36, Math.sin(angle) * 0.36, 0]}
                            >
                              <boxGeometry args={[0.65, 0.045, 0.045]} />
                              <meshStandardMaterial color="#8b9d93" metalness={0.8} roughness={0.3} />
                            </mesh>
                          ))}
                          <mesh position={[0.66, 0, 0.12]}>
                            <sphereGeometry args={[0.09, 16, 12]} />
                            <meshStandardMaterial color="#d49b42" />
                          </mesh>
                        </group>
                      )}
                    </group>
                  </group>
                )}
                {part === 'bearing' && <Bearing selected={selected === part} />}
              </group>
              {!installed && (
                <Html position={[0, part === 'housing' ? 1.3 : 0.85, 0]} center>
                  <button
                    style={{
                      ...hotspotStyle,
                      background: state.heldPart === part ? '#ffe699' : '#ffffff',
                      fontSize: 11,
                    }}
                    onClick={() => {
                      onSelect(part);
                      action(`pick:${part}`);
                    }}
                  >
                    Pick {labels[part]}
                  </button>
                </Html>
              )}
            </MovingGroup>
          </group>
        );
      })}

      {nextPart && (
        <group
          position={placedPosition(nextPart)}
          onClick={event => {
            event.stopPropagation();
            action(`place:${nextPart}`);
          }}
        >
          {nextPart === 'base' ? (
            <mesh>
              <boxGeometry args={[3.3, 0.28, 2.75]} />
              <meshBasicMaterial color="#38a169" transparent opacity={0.25} wireframe />
            </mesh>
          ) : (
            <mesh rotation={[0, Math.PI / 2, 0]}>
              <torusGeometry
                args={[nextPart === 'housing' ? 1.06 : nextPart === 'shaft' ? 0.35 : 0.77, 0.035, 8, 48]}
              />
              <meshBasicMaterial color="#38a169" transparent opacity={0.7} />
            </mesh>
          )}
          {state.heldPart && objective.action === `place:${nextPart}` && (
            <Html position={[0, 1.7, 0]} center>
              <button style={hotspotStyle} onClick={() => action(`place:${nextPart}`)}>
                Place {labels[nextPart]} here
              </button>
            </Html>
          )}
        </group>
      )}

      {state.placed.bearing && state.seatDepth < 3 && (
        <Html position={[1.75, 2.7, 0]} center>
          <button style={hotspotStyle} onClick={() => action('press')}>
            Press bearing · {state.seatDepth}/3
          </button>
        </Html>
      )}

      {state.tool === 'bearing-sleeve' && state.placed.bearing && state.seatDepth < 3 && (
        <group
          onClick={event => {
            event.stopPropagation();
            action('press');
          }}
        >
          <MovingGroup target={[2.07 - state.seatDepth * 0.5, 1.38, 0]}>
            <mesh rotation={[0, Math.PI / 2, 0]} castShadow>
              <torusGeometry args={[0.46, 0.09, 16, 48]} />
              <meshStandardMaterial color="#be984d" metalness={0.7} roughness={0.3} />
            </mesh>
            <mesh rotation={[0, 0, Math.PI / 2]} position={[0.18, 0.46, 0]} castShadow>
              <cylinderGeometry args={[0.075, 0.075, 0.6, 16]} />
              <meshStandardMaterial color="#be984d" metalness={0.7} roughness={0.3} />
            </mesh>
          </MovingGroup>
        </group>
      )}

      {state.tool === 'alignment-jig' && state.placed.housing && !state.placed.shaft && (
        <Html position={[1, 3.25, 0]} center>
          <div style={{ ...hotspotStyle, cursor: 'default', display: 'flex', alignItems: 'center', gap: 10 }}>
            <button aria-label="Scene alignment left" onClick={() => action('adjust:left')}>
              ←
            </button>
            <span>Alignment {state.alignment > 0 ? '+' : ''}{state.alignment}</span>
            <button aria-label="Scene alignment right" onClick={() => action('adjust:right')}>
              →
            </button>
          </div>
        </Html>
      )}

      {state.bolts.length === 4 && state.turns < 3 && (
        <Html position={[2.8, 2.6, 0]} center>
          <button style={hotspotStyle} onClick={() => action('turn')}>
            Turn handwheel · {state.turns}/3
          </button>
        </Html>
      )}

      {Object.entries(trayPositions).map(
        ([part, [x, , z]]) =>
          !state.placed[part as Part] && (
            <mesh key={part} position={[x, 0.035, z]} receiveShadow>
              <boxGeometry args={[part === 'shaft' ? 4.4 : 2.35, 0.06, part === 'shaft' ? 0.9 : 2.1]} />
              <meshStandardMaterial color="#d8ded6" roughness={0.95} />
            </mesh>
          )
      )}
    </>
  );
}

function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2');
    if (!context) return false;
    context.getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function SceneLifecycle({
  resetKey,
  onContextLost,
  workshop,
}: {
  resetKey: number;
  onContextLost: () => void;
  workshop: boolean;
}) {
  const { camera, controls, gl } = useThree();
  useEffect(() => {
    const orbit = controls as { reset: () => void; target: THREE.Vector3; update: () => void } | null;
    orbit?.reset();
    const target = workshop ? new THREE.Vector3(0, 0.9, 0) : new THREE.Vector3(0.35, 1.2, 0);
    if (workshop) camera.position.set(8.8, 7, 9);
    else camera.position.set(6.4, 4.7, 6.3);
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = workshop ? 40 : 37;
      camera.updateProjectionMatrix();
    }
    camera.lookAt(target);
    orbit?.target.copy(target);
    orbit?.update();
  }, [camera, controls, resetKey, workshop]);

  useEffect(() => {
    const canvas = gl.domElement;
    const lost = (event: Event) => {
      event.preventDefault();
      onContextLost();
    };
    canvas.addEventListener('webglcontextlost', lost);
    return () => canvas.removeEventListener('webglcontextlost', lost);
  }, [gl, onContextLost]);

  return null;
}

export default function AssemblyScene(props: Props) {
  const [webGLAvailable] = useState(supportsWebGL);
  const [contextLost, setContextLost] = useState(false);
  const fallback = <Fallback {...props} />;

  if (!webGLAvailable || contextLost) return fallback;

  return (
    <div
      style={{ width: '100%', height: '100%', minHeight: 0 }}
      role="group"
      aria-label="Interactive 3D bearing assembly. Select components by clicking them; drag to orbit and scroll to zoom."
    >
      <SceneBoundary fallback={fallback}>
        <Canvas
          frameloop="demand"
          shadows
          dpr={[1, 1.75]}
          camera={{ position: props.workshop ? [8.8, 7, 9] : [6.4, 4.7, 6.3], fov: props.workshop ? 40 : 37 }}
          gl={{ antialias: true, alpha: false }}
          fallback={fallback}
        >
          <color attach="background" args={['#edf0ec']} />
          <fog attach="fog" args={['#edf0ec', 16, 28]} />
          <ambientLight intensity={1.5} />
          <hemisphereLight args={['#ffffff', '#7f9185', 2.3]} />
          <directionalLight
            position={[3, 8, 4]}
            intensity={4.0}
            castShadow
            shadow-mapSize={[2048, 2048]}
            shadow-camera-left={-6}
            shadow-camera-right={6}
            shadow-camera-top={6}
            shadow-camera-bottom={-6}
            shadow-bias={-0.0005}
          />
          <directionalLight position={[-5, 4, -3]} intensity={2.2} color="#dce7f0" />
          {props.workshop ? <WorkshopAssembly {...props} workshop={props.workshop} /> : <Assembly {...props} />}
          <gridHelper args={[30, 60, '#c7d1c8', '#dbe0d9']} position={[0, 0.005, 0]} />
          <ContactShadows position={[0, 0.01, 0]} opacity={0.28} scale={14} blur={2.2} far={5} resolution={256} />
          <OrbitControls
            makeDefault
            target={props.workshop ? [0, 0.9, 0] : [0.35, 1.2, 0]}
            minDistance={5.5}
            maxDistance={props.workshop ? 17 : 13}
            minPolarAngle={0.3}
            maxPolarAngle={Math.PI / 2.1}
            enablePan={false}
            enableDamping={false}
          />
          <SceneLifecycle
            resetKey={props.resetKey}
            onContextLost={() => setContextLost(true)}
            workshop={Boolean(props.workshop)}
          />
        </Canvas>
      </SceneBoundary>
    </div>
  );
}
